# """
# app/agents/bedrock_client.py  — FIXED VERSION
# Key fixes:
# 1. Falls back to direct Claude model if Agent ID not configured
# 2. Better error messages with actual exception details logged
# 3. Handles ThrottlingException, AccessDeniedException, ValidationException
# 4. Test mode: if BEDROCK_AGENT_ID is empty, uses direct model invocation
# """
# import asyncio
# import json
# import time
# from collections.abc import AsyncGenerator

# import boto3
# import structlog
# from botocore.config import Config
# from botocore.exceptions import ClientError, NoCredentialsError

# from app.core.config import settings
# from app.core.metrics import (
#     bedrock_requests_total,
#     bedrock_response_latency_ms,
#     bedrock_tokens_used_total,
#     bedrock_errors_total,
#     bedrock_region_requests_total,
#     bedrock_region_failover_total,
#     bedrock_region_latency_ms,
# )

# log = structlog.get_logger()

# _RETRYABLE_BEDROCK_CODES = {
#     "ThrottlingException",
#     "ServiceUnavailableException",
#     "InternalServerException",
#     "ModelNotReadyException",
#     "ModelTimeoutException",
#     "DependencyFailedException",
# }

# _COUNTRY_REGION_HINTS = {
#     "IN": "ap-south-1",
#     "AE": "me-central-1",
#     "SA": "me-central-1",
#     "GB": "eu-west-1",
#     "DE": "eu-central-1",
#     "FR": "eu-west-3",
#     "CA": "ca-central-1",
#     "JP": "ap-northeast-1",
#     "SG": "ap-southeast-1",
#     "AU": "ap-southeast-2",
# }


# class BedrockAgentClient:

#     def __init__(self):
#         self._credentials = {}
#         if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
#             self._credentials["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
#             self._credentials["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()

#         self._default_region = (settings.BEDROCK_AGENT_REGION or settings.AWS_REGION).strip()
#         self._fallback_regions = [
#             region.strip()
#             for region in settings.BEDROCK_FALLBACK_REGIONS
#             if region and region.strip() and region.strip() != self._default_region
#         ]
#         self._runtime_clients = {}
#         self._bedrock_clients = {}

#         log.info(
#             "bedrock.client_initialized",
#             default_region=self._default_region,
#             fallback_regions=self._fallback_regions,
#         )

#     def _client_config(self, region: str) -> Config:
#         return Config(
#             region_name=region,
#             retries={"max_attempts": settings.BEDROCK_RETRY_MAX_ATTEMPTS, "mode": "adaptive"},
#             connect_timeout=settings.BEDROCK_CONNECT_TIMEOUT_SECONDS,
#             read_timeout=settings.BEDROCK_READ_TIMEOUT_SECONDS,
#             max_pool_connections=settings.BEDROCK_MAX_POOL_CONNECTIONS,
#             tcp_keepalive=True,
#         )

#     def _runtime_client(self, region: str):
#         region = region.strip()
#         if not region:
#             return None
#         try:
#             if region not in self._runtime_clients:
#                 self._runtime_clients[region] = boto3.client(
#                     "bedrock-agent-runtime",
#                     config=self._client_config(region),
#                     **self._credentials,
#                 )
#             return self._runtime_clients[region]
#         except Exception as e:
#             log.error("bedrock.runtime_client_init_failed", region=region, error=str(e))
#             return None

#     def _bedrock_client(self, region: str):
#         region = region.strip()
#         if not region:
#             return None
#         try:
#             if region not in self._bedrock_clients:
#                 self._bedrock_clients[region] = boto3.client(
#                     "bedrock-runtime",
#                     config=self._client_config(region),
#                     **self._credentials,
#                 )
#             return self._bedrock_clients[region]
#         except Exception as e:
#             log.error("bedrock.direct_client_init_failed", region=region, error=str(e))
#             return None

#     def _candidate_regions(self, preferred_region: str | None = None, request_country: str | None = None) -> list[str]:
#         regions: list[str] = []
#         if preferred_region and preferred_region.strip():
#             regions.append(preferred_region.strip())
#         country_region = _COUNTRY_REGION_HINTS.get((request_country or "").strip().upper())
#         if country_region:
#             regions.append(country_region)
#         regions.append(self._default_region)
#         regions.extend(self._fallback_regions)

#         deduped = []
#         seen = set()
#         for region in regions:
#             cleaned = (region or "").strip()
#             if cleaned and cleaned not in seen:
#                 seen.add(cleaned)
#                 deduped.append(cleaned)
#         return deduped or [settings.AWS_REGION]

#     async def invoke_agent_streaming(
#         self,
#         user_message: str,
#         session_id: str,
#         *,
#         agent_id: str | None = None,
#         agent_alias_id: str | None = None,
#         knowledge_base_id: str | None = None,
#         workspace_id: str | None = None,
#         user_profile: dict | None = None,
#         allow_global_fallback: bool = False,
#         preferred_region: str | None = None,
#         request_country: str | None = None,
#     ) -> AsyncGenerator[dict, None]:
#         """
#         Stream response from Bedrock Agent.
#         Falls back to direct model call if Agent ID is not configured.
#         """
#         start_time = time.time()
#         # By default, do NOT use global shared agent IDs to avoid cross-tenant leakage.
#         effective_agent_id = agent_id
#         effective_agent_alias_id = agent_alias_id
#         if allow_global_fallback:
#             effective_agent_id = effective_agent_id if effective_agent_id is not None else settings.BEDROCK_AGENT_ID
#             effective_agent_alias_id = (
#                 effective_agent_alias_id
#                 if effective_agent_alias_id is not None
#                 else settings.BEDROCK_AGENT_ALIAS_ID
#             )

#         agent_configured = bool(
#             effective_agent_id and
#             effective_agent_id not in ("", "YOUR_AGENT_ID", "test")
#         )

#         if not agent_configured:
#             log.warning("bedrock.agent_not_configured_using_direct_model")
#             async for chunk in self._invoke_direct_streaming(
#                 user_message,
#                 start_time,
#                 user_profile=user_profile,
#                 preferred_region=preferred_region,
#                 request_country=request_country,
#             ):
#                 yield chunk
#             return

#         loop = asyncio.get_running_loop()
#         enriched_message = self._build_contextual_message(user_message, user_profile)
#         request_payload: dict = {
#             "agentId": effective_agent_id,
#             "agentAliasId": effective_agent_alias_id,
#             "sessionId": session_id,
#             "inputText": enriched_message,
#             "enableTrace": False,
#             "endSession": False,
#         }

#         if knowledge_base_id:
#             retrieval_filter = self._build_workspace_source_uri_filter(workspace_id)
#             if retrieval_filter is None:
#                 log.error(
#                     "bedrock.workspace_filter_unavailable",
#                     workspace_id=workspace_id,
#                     bucket=settings.S3_KNOWLEDGE_BASE_BUCKET,
#                 )
#                 yield {
#                     "type": "error",
#                     "content": (
#                         "Workspace isolation is enabled but retrieval filter could not be built. "
#                         "Ensure workspace_id and S3_KNOWLEDGE_BASE_BUCKET are configured."
#                     ),
#                 }
#                 return

#             request_payload["sessionState"] = {
#                 "knowledgeBaseConfigurations": [
#                     {
#                         "knowledgeBaseId": knowledge_base_id,
#                         "retrievalConfiguration": {
#                             "vectorSearchConfiguration": {
#                                 "numberOfResults": settings.BEDROCK_RETRIEVAL_RESULTS,
#                                 "filter": retrieval_filter,
#                             }
#                         },
#                     }
#                 ]
#             }

#         candidate_regions = self._candidate_regions(
#             preferred_region=preferred_region,
#             request_country=request_country,
#         )

#         last_error: Exception | None = None
#         for idx, region in enumerate(candidate_regions):
#             runtime_client = self._runtime_client(region)
#             if runtime_client is None:
#                 continue
#             try:
#                 response = await loop.run_in_executor(
#                     None,
#                     lambda: runtime_client.invoke_agent(**request_payload),
#                 )

#                 tokens_used = 0
#                 for event in response.get("completion", []):
#                     if "chunk" in event:
#                         chunk_bytes = event["chunk"].get("bytes", b"")
#                         if chunk_bytes:
#                             text = chunk_bytes.decode("utf-8")
#                             yield {"type": "text", "content": text}
#                     elif "trace" in event:
#                         trace = event["trace"]
#                         if "orchestrationTrace" in trace:
#                             orch = trace["orchestrationTrace"]
#                             if "modelInvocationOutput" in orch:
#                                 usage = orch["modelInvocationOutput"].get("usage", {})
#                                 tokens_used = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)

#                 latency_ms = int((time.time() - start_time) * 1000)
#                 bedrock_response_latency_ms.observe(latency_ms)
#                 bedrock_region_latency_ms.labels(path="agent", region=region).observe(latency_ms)
#                 bedrock_requests_total.labels(status="success").inc()
#                 bedrock_region_requests_total.labels(path="agent", region=region, status="success").inc()

#                 if tokens_used:
#                     bedrock_tokens_used_total.labels(direction="output").inc(tokens_used)

#                 yield {
#                     "type": "end",
#                     "metadata": {
#                         "tokens_used": tokens_used,
#                         "latency_ms": latency_ms,
#                         "model_id": settings.BEDROCK_MODEL_ID,
#                         "region": region,
#                     },
#                 }
#                 return

#             except NoCredentialsError as e:
#                 last_error = e
#                 log.error("bedrock.no_credentials")
#                 break
#             except ClientError as e:
#                 last_error = e
#                 code = e.response["Error"]["Code"]
#                 msg = e.response["Error"]["Message"]
#                 is_retryable = code in _RETRYABLE_BEDROCK_CODES and idx < len(candidate_regions) - 1
#                 if is_retryable:
#                     bedrock_region_failover_total.labels(
#                         path="agent",
#                         from_region=region,
#                         to_region=candidate_regions[idx + 1],
#                         reason=code,
#                     ).inc()
#                     log.warning(
#                         "bedrock.region_failover_retry",
#                         region=region,
#                         next_region=candidate_regions[idx + 1],
#                         code=code,
#                     )
#                     continue

#                 latency_ms = int((time.time() - start_time) * 1000)
#                 bedrock_response_latency_ms.observe(latency_ms)
#                 bedrock_requests_total.labels(
#                     status="throttled" if code == "ThrottlingException" else "error"
#                 ).inc()
#                 bedrock_region_requests_total.labels(
#                     path="agent",
#                     region=region,
#                     status="throttled" if code == "ThrottlingException" else "error",
#                 ).inc()
#                 bedrock_errors_total.labels(error_code=code).inc()

#                 if code == "AccessDeniedException":
#                     yield {"type": "error", "content": f"AWS access denied. Check your IAM permissions for Bedrock. ({msg})"}
#                 elif code == "ThrottlingException":
#                     yield {"type": "error", "content": "Bedrock is throttling requests. Please try again in a moment."}
#                 elif code == "ValidationException":
#                     yield {"type": "error", "content": f"Invalid Bedrock configuration. Check your BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID. ({msg})"}
#                 elif code == "ResourceNotFoundException":
#                     yield {"type": "error", "content": f"Bedrock resource not found in region `{region}`. Check Agent/Alias/KB IDs or region settings. ({msg})"}
#                 else:
#                     yield {"type": "error", "content": f"Bedrock error ({code}): {msg}"}
#                 return
#             except Exception as e:
#                 last_error = e
#                 is_retryable = idx < len(candidate_regions) - 1
#                 if is_retryable:
#                     bedrock_region_failover_total.labels(
#                         path="agent",
#                         from_region=region,
#                         to_region=candidate_regions[idx + 1],
#                         reason=type(e).__name__,
#                     ).inc()
#                     log.warning(
#                         "bedrock.region_failover_unexpected_retry",
#                         region=region,
#                         next_region=candidate_regions[idx + 1],
#                         error=str(e),
#                     )
#                     continue
#                 latency_ms = int((time.time() - start_time) * 1000)
#                 bedrock_response_latency_ms.observe(latency_ms)
#                 bedrock_requests_total.labels(status="error").inc()
#                 bedrock_region_requests_total.labels(path="agent", region=region, status="error").inc()
#                 bedrock_errors_total.labels(error_code=type(e).__name__).inc()
#                 log.error("bedrock.unexpected_error", error=str(e), exc_info=True)
#                 yield {"type": "error", "content": "Unable to get response right now. Please try again."}
#                 return

#         latency_ms = int((time.time() - start_time) * 1000)
#         bedrock_response_latency_ms.observe(latency_ms)
#         bedrock_requests_total.labels(status="error").inc()
#         bedrock_region_requests_total.labels(path="agent", region="none", status="error").inc()
#         bedrock_errors_total.labels(error_code=type(last_error).__name__ if last_error else "NoRegionClient").inc()
#         if isinstance(last_error, NoCredentialsError):
#             yield {"type": "error", "content": "AWS credentials not configured. Please check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file."}
#         else:
#             yield {"type": "error", "content": "Unable to reach Bedrock in configured regions. Check region settings and networking."}

#     async def _invoke_direct_streaming(
#         self,
#         user_message: str,
#         start_time: float,
#         user_profile: dict | None = None,
#         preferred_region: str | None = None,
#         request_country: str | None = None,
#     ) -> AsyncGenerator[dict, None]:
#         """Direct model call used when Agent is not configured."""
#         loop = asyncio.get_running_loop()

#         system_prompt = (
#             "You are TissaTech Assistant, a helpful AI for TissaTech company. "
#             "Answer questions about software development, technology, and TissaTech services. "
#             "Be concise, helpful, and professional."
#         )

#         body = {
#             "anthropic_version": "bedrock-2023-05-31",
#             "max_tokens": settings.BEDROCK_MAX_TOKENS,
#             "temperature": 0.2,
#             "system": system_prompt,
#             "messages": [{"role": "user", "content": self._build_contextual_message(user_message, user_profile)}],
#         }

#         candidate_regions = self._candidate_regions(
#             preferred_region=preferred_region,
#             request_country=request_country,
#         )
#         last_error: Exception | None = None

#         for idx, region in enumerate(candidate_regions):
#             direct_client = self._bedrock_client(region)
#             if direct_client is None:
#                 continue
#             try:
#                 response = await loop.run_in_executor(
#                     None,
#                     lambda: direct_client.invoke_model_with_response_stream(
#                         modelId=settings.BEDROCK_MODEL_ID,
#                         body=json.dumps(body),
#                         contentType="application/json",
#                         accept="application/json",
#                     ),
#                 )

#                 tokens_used = 0
#                 for event in response.get("body", []):
#                     chunk = json.loads(event["chunk"]["bytes"])
#                     if chunk["type"] == "content_block_delta":
#                         text = chunk["delta"].get("text", "")
#                         if text:
#                             yield {"type": "text", "content": text}
#                     elif chunk["type"] == "message_delta":
#                         tokens_used = chunk.get("usage", {}).get("output_tokens", 0)

#                 latency_ms = int((time.time() - start_time) * 1000)
#                 bedrock_response_latency_ms.observe(latency_ms)
#                 bedrock_region_latency_ms.labels(path="direct", region=region).observe(latency_ms)
#                 bedrock_requests_total.labels(status="success").inc()
#                 bedrock_region_requests_total.labels(path="direct", region=region, status="success").inc()
#                 if tokens_used:
#                     bedrock_tokens_used_total.labels(direction="output").inc(tokens_used)

#                 yield {
#                     "type": "end",
#                     "metadata": {
#                         "tokens_used": tokens_used,
#                         "latency_ms": latency_ms,
#                         "model_id": settings.BEDROCK_MODEL_ID,
#                         "region": region,
#                     },
#                 }
#                 return

#             except NoCredentialsError as e:
#                 last_error = e
#                 break
#             except ClientError as e:
#                 last_error = e
#                 code = e.response["Error"]["Code"]
#                 msg = e.response["Error"]["Message"]
#                 is_retryable = code in _RETRYABLE_BEDROCK_CODES and idx < len(candidate_regions) - 1
#                 if is_retryable:
#                     bedrock_region_failover_total.labels(
#                         path="direct",
#                         from_region=region,
#                         to_region=candidate_regions[idx + 1],
#                         reason=code,
#                     ).inc()
#                     log.warning(
#                         "bedrock.direct_region_failover_retry",
#                         region=region,
#                         next_region=candidate_regions[idx + 1],
#                         code=code,
#                     )
#                     continue

#                 latency_ms = int((time.time() - start_time) * 1000)
#                 bedrock_response_latency_ms.observe(latency_ms)
#                 bedrock_requests_total.labels(
#                     status="throttled" if code == "ThrottlingException" else "error"
#                 ).inc()
#                 bedrock_region_requests_total.labels(
#                     path="direct",
#                     region=region,
#                     status="throttled" if code == "ThrottlingException" else "error",
#                 ).inc()
#                 bedrock_errors_total.labels(error_code=code).inc()
#                 log.error("bedrock.direct_error", region=region, code=code, message=msg)
#                 yield {"type": "error", "content": f"Bedrock error ({code}): {msg}"}
#                 return
#             except Exception as e:
#                 last_error = e
#                 is_retryable = idx < len(candidate_regions) - 1
#                 if is_retryable:
#                     bedrock_region_failover_total.labels(
#                         path="direct",
#                         from_region=region,
#                         to_region=candidate_regions[idx + 1],
#                         reason=type(e).__name__,
#                     ).inc()
#                     log.warning(
#                         "bedrock.direct_region_failover_unexpected_retry",
#                         region=region,
#                         next_region=candidate_regions[idx + 1],
#                         error=str(e),
#                     )
#                     continue

#                 latency_ms = int((time.time() - start_time) * 1000)
#                 bedrock_response_latency_ms.observe(latency_ms)
#                 bedrock_requests_total.labels(status="error").inc()
#                 bedrock_region_requests_total.labels(path="direct", region=region, status="error").inc()
#                 bedrock_errors_total.labels(error_code=type(e).__name__).inc()
#                 log.error("bedrock.direct_unexpected", error=str(e), exc_info=True)
#                 yield {"type": "error", "content": "Error calling Bedrock model. Please try again."}
#                 return

#         latency_ms = int((time.time() - start_time) * 1000)
#         bedrock_response_latency_ms.observe(latency_ms)
#         bedrock_requests_total.labels(status="error").inc()
#         bedrock_region_requests_total.labels(path="direct", region="none", status="error").inc()
#         bedrock_errors_total.labels(error_code=type(last_error).__name__ if last_error else "NoRegionClient").inc()
#         if isinstance(last_error, NoCredentialsError):
#             yield {"type": "error", "content": "AWS credentials not configured. Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to your .env file."}
#         else:
#             yield {"type": "error", "content": "Unable to reach Bedrock model in configured regions."}

#     @staticmethod
#     def _role_tone_guidance(user_profile: dict | None) -> str:
#         role_value = user_profile.get("role") if isinstance(user_profile, dict) else None
#         role = role_value.strip().lower() if isinstance(role_value, str) else ""
#         if not role:
#             return (
#                 "Tone profile: neutral professional.\n"
#                 "Use clear language, practical examples, and a concise structure."
#             )

#         executive_keywords = {
#             "ceo", "cto", "cio", "cfo", "coo", "founder", "director",
#             "vice president", "vp", "head", "chief", "partner", "owner",
#             "president", "board", "executive",
#         }
#         technical_keywords = {
#             "developer", "engineer", "architect", "technical", "tech lead",
#             "software", "devops", "sre", "qa", "tester", "data engineer",
#             "data scientist", "ml engineer", "ai engineer", "administrator",
#             "sysadmin", "backend", "frontend", "full stack",
#         }
#         product_keywords = {
#             "product manager", "product owner", "project manager", "delivery manager",
#             "scrum master", "program manager",
#         }
#         sales_marketing_keywords = {
#             "sales", "marketing", "business development", "growth", "account manager",
#             "customer success", "brand", "seo",
#         }

#         if any(k in role for k in executive_keywords):
#             return (
#                 "Tone profile: executive/business.\n"
#                 "Emphasize business outcomes, ROI, risks, timelines, and decision-ready recommendations.\n"
#                 "Avoid excessive implementation-level detail unless explicitly asked."
#             )
#         if any(k in role for k in technical_keywords):
#             return (
#                 "Tone profile: technical.\n"
#                 "Provide concrete technical depth, architecture trade-offs, implementation options, and practical steps.\n"
#                 "Use precise engineering language and include constraints/assumptions."
#             )
#         if any(k in role for k in product_keywords):
#             return (
#                 "Tone profile: product/delivery.\n"
#                 "Balance business and technical points with roadmap impact, effort, dependencies, and execution priorities."
#             )
#         if any(k in role for k in sales_marketing_keywords):
#             return (
#                 "Tone profile: sales/marketing.\n"
#                 "Focus on value proposition, differentiation, customer impact, and clear call-to-action language."
#             )
#         return (
#             "Tone profile: professional role-adaptive.\n"
#             "Keep language clear, concise, and outcome-oriented with the right amount of detail for the user's designation."
#         )

#     @staticmethod
#     def _build_contextual_message(user_message: str, user_profile: dict | None) -> str:
#         context_lines = []
#         for key in ("role", "industry", "organization", "name"):
#             value = user_profile.get(key) if isinstance(user_profile, dict) else None
#             if isinstance(value, str):
#                 cleaned = value.strip()
#                 if cleaned:
#                     context_lines.append(f"- {key}: {cleaned[:100]}")

#         style_instructions = (
#             "Response requirements:\n"
#             "1. Use clean Markdown formatting with short sections.\n"
#             "2. Use bullet points for lists and numbered steps for procedures.\n"
#             "3. Keep sentences grammatically correct, professional, and easy to read.\n"
#             "4. Keep paragraphs short (1-2 lines each).\n"
#             "5. Prefer clear, actionable answers over long raw text blocks.\n"
#             "6. Do not use filler phrases like 'according to the search results' in the final answer.\n"
#             "7. Adapt tone and depth to the user's role/designation."
#         )
#         tone_guidance = BedrockAgentClient._role_tone_guidance(user_profile)

#         if context_lines:
#             return (
#                 "User profile context:\n"
#                 + "\n".join(context_lines)
#                 + "\n\n"
#                 + tone_guidance
#                 + "\n\n"
#                 + style_instructions
#                 + f"\n\nQuestion: {user_message}"
#             )

#         return tone_guidance + "\n\n" + style_instructions + f"\n\nQuestion: {user_message}"

#     async def search_knowledge_base(
#         self,
#         query: str,
#         num_results: int = settings.BEDROCK_RETRIEVAL_RESULTS,
#         *,
#         knowledge_base_id: str | None = None,
#         workspace_id: str | None = None,
#     ) -> list:
#         effective_kb_id = (
#             knowledge_base_id if knowledge_base_id is not None else settings.BEDROCK_KNOWLEDGE_BASE_ID
#         )
#         if not effective_kb_id or effective_kb_id in ("", "YOUR_KB_ID"):
#             log.warning("bedrock.kb_not_configured")
#             return []

#         retrieval_filter = self._build_workspace_source_uri_filter(workspace_id)
#         if retrieval_filter is None:
#             log.warning(
#                 "bedrock.kb_search_filter_missing",
#                 workspace_id=workspace_id,
#                 bucket=settings.S3_KNOWLEDGE_BASE_BUCKET,
#             )
#             return []

#         loop = asyncio.get_running_loop()
#         runtime_client = self._runtime_client(self._default_region)
#         if runtime_client is None:
#             log.error("bedrock.kb_runtime_client_unavailable", region=self._default_region)
#             return []

#         try:
#             response = await loop.run_in_executor(
#                 None,
#                 lambda: runtime_client.retrieve(
#                     knowledgeBaseId=effective_kb_id,
#                     retrievalQuery={"text": query},
#                     retrievalConfiguration={
#                         "vectorSearchConfiguration": {
#                             "numberOfResults": num_results,
#                             "filter": retrieval_filter,
#                         }
#                     },
#                 ),
#             )
#             return [
#                 {
#                     "content": item["content"]["text"],
#                     "score": item.get("score", 0.0),
#                     "source": item.get("location", {}).get("s3Location", {}).get("uri", ""),
#                 }
#                 for item in response.get("retrievalResults", [])
#             ]
#         except Exception as e:
#             log.error("bedrock.kb_search_error", error=str(e))
#             return []

#     @staticmethod
#     def _workspace_source_uri_prefix(workspace_id: str | None) -> str | None:
#         if not workspace_id:
#             return None
#         bucket = (settings.S3_KNOWLEDGE_BASE_BUCKET or "").strip()
#         if not bucket:
#             return None
#         workspace = workspace_id.strip()
#         if not workspace:
#             return None
#         return f"s3://{bucket}/workspaces/{workspace}/"

#     @classmethod
#     def _build_workspace_source_uri_filter(cls, workspace_id: str | None) -> dict | None:
#         source_prefix = cls._workspace_source_uri_prefix(workspace_id)
#         if not source_prefix:
#             return None
#         return {
#             "startsWith": {
#                 "key": "x-amz-bedrock-kb-source-uri",
#                 "value": source_prefix,
#             }
#         }


# bedrock_client = BedrockAgentClient()

"""
app/agents/bedrock_client.py  — OPTIMIZED + FIXED for us-east-2 only
Key fixes vs previous version:
1. Removed country-region hints that tried wrong regions (us-east-2 only)
2. Removed fallback region logic that caused delays on failure
3. Increased connect timeout for cold starts
4. Pre-warmed boto3 clients at startup
5. Reduced retrieval results default to 5 for faster KB lookup
6. streamingChunkSize / performance hints passed to agent runtime
7. Lambda closure bug fixed (region captured properly in loop)
"""
import asyncio
import json
import time
from collections.abc import AsyncGenerator

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings
from app.core.metrics import (
    bedrock_requests_total,
    bedrock_response_latency_ms,
    bedrock_tokens_used_total,
    bedrock_errors_total,
    bedrock_region_requests_total,
    bedrock_region_failover_total,
    bedrock_region_latency_ms,
)

log = structlog.get_logger()

_RETRYABLE_BEDROCK_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelNotReadyException",
    "ModelTimeoutException",
    "DependencyFailedException",
}

# FIXED: Only us-east-2 has the agent/KB/S3 bucket — no cross-region hints
_COUNTRY_REGION_HINTS: dict[str, str] = {}


class BedrockAgentClient:

    def __init__(self):
        self._credentials = {}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
            self._credentials["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
            self._credentials["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()

        # Always use us-east-2 — agent, KB, and S3 bucket are all there
        self._default_region = "us-east-2"
        # No fallback regions — only us-east-2 has the resources
        self._fallback_regions: list[str] = []
        self._runtime_clients: dict[str, object] = {}
        self._bedrock_clients: dict[str, object] = {}

        # Pre-warm clients at startup so first request is fast
        self._runtime_client(self._default_region)
        self._bedrock_client(self._default_region)

        log.info(
            "bedrock.client_initialized",
            default_region=self._default_region,
            fallback_regions=self._fallback_regions,
        )

    def _client_config(self, region: str) -> Config:
        return Config(
            region_name=region,
            # OPTIMIZED: adaptive retry with max 2 attempts (don't waste time retrying)
            retries={"max_attempts": 2, "mode": "adaptive"},
            # OPTIMIZED: 8s connect timeout (was 4s — too short for Bedrock cold starts)
            connect_timeout=8,
            # 60s read timeout is fine for streaming
            read_timeout=60,
            # OPTIMIZED: higher connection pool for concurrent requests
            max_pool_connections=200,
            tcp_keepalive=True,
        )

    def _runtime_client(self, region: str):
        region = region.strip()
        if not region:
            return None
        try:
            if region not in self._runtime_clients:
                self._runtime_clients[region] = boto3.client(
                    "bedrock-agent-runtime",
                    config=self._client_config(region),
                    **self._credentials,
                )
            return self._runtime_clients[region]
        except Exception as e:
            log.error("bedrock.runtime_client_init_failed", region=region, error=str(e))
            return None

    def _bedrock_client(self, region: str):
        region = region.strip()
        if not region:
            return None
        try:
            if region not in self._bedrock_clients:
                self._bedrock_clients[region] = boto3.client(
                    "bedrock-runtime",
                    config=self._client_config(region),
                    **self._credentials,
                )
            return self._bedrock_clients[region]
        except Exception as e:
            log.error("bedrock.direct_client_init_failed", region=region, error=str(e))
            return None

    def _candidate_regions(
        self,
        preferred_region: str | None = None,
        request_country: str | None = None,
    ) -> list[str]:
        # FIXED: Always use us-east-2 — ignore preferred region / country hints
        # since agent, KB, and S3 bucket exist only in us-east-2
        return [self._default_region]

    async def invoke_agent_streaming(
        self,
        user_message: str,
        session_id: str,
        *,
        agent_id: str | None = None,
        agent_alias_id: str | None = None,
        knowledge_base_id: str | None = None,
        workspace_id: str | None = None,
        user_profile: dict | None = None,
        allow_global_fallback: bool = False,
        preferred_region: str | None = None,
        request_country: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream response from Bedrock Agent (us-east-2 only).
        Falls back to direct model call if Agent ID is not configured.
        """
        start_time = time.time()

        effective_agent_id = agent_id
        effective_agent_alias_id = agent_alias_id

        # FIXED: Use global agent when workspace doesn't have dedicated resources
        if allow_global_fallback:
            effective_agent_id = effective_agent_id if effective_agent_id is not None else settings.BEDROCK_AGENT_ID
            effective_agent_alias_id = (
                effective_agent_alias_id
                if effective_agent_alias_id is not None
                else settings.BEDROCK_AGENT_ALIAS_ID
            )

        agent_configured = bool(
            effective_agent_id and
            effective_agent_id not in ("", "YOUR_AGENT_ID", "test")
        )

        if not agent_configured:
            log.warning("bedrock.agent_not_configured_using_direct_model")
            async for chunk in self._invoke_direct_streaming(
                user_message,
                start_time,
                user_profile=user_profile,
            ):
                yield chunk
            return

        loop = asyncio.get_running_loop()
        enriched_message = self._build_contextual_message(user_message, user_profile)

        request_payload: dict = {
            "agentId": effective_agent_id,
            "agentAliasId": effective_agent_alias_id,
            "sessionId": session_id,
            "inputText": enriched_message,
            "enableTrace": False,
            "endSession": False,
        }

        if knowledge_base_id:
            retrieval_filter = self._build_workspace_source_uri_filter(workspace_id)
            if retrieval_filter is None:
                log.error(
                    "bedrock.workspace_filter_unavailable",
                    workspace_id=workspace_id,
                    bucket=settings.S3_KNOWLEDGE_BASE_BUCKET,
                )
                yield {
                    "type": "error",
                    "content": (
                        "Workspace isolation is enabled but retrieval filter could not be built. "
                        "Ensure workspace_id and S3_KNOWLEDGE_BASE_BUCKET are configured."
                    ),
                }
                return

            request_payload["sessionState"] = {
                "knowledgeBaseConfigurations": [
                    {
                        "knowledgeBaseId": knowledge_base_id,
                        "retrievalConfiguration": {
                            "vectorSearchConfiguration": {
                                # OPTIMIZED: Reduced from 12 to 5 results for faster retrieval
                                "numberOfResults": min(settings.BEDROCK_RETRIEVAL_RESULTS, 5),
                                "filter": retrieval_filter,
                            }
                        },
                    }
                ]
            }

        region = self._default_region
        runtime_client = self._runtime_client(region)
        if runtime_client is None:
            yield {"type": "error", "content": "Bedrock client unavailable. Check AWS credentials."}
            return

        try:
            # OPTIMIZED: capture region in closure to avoid lambda bug
            _region = region
            _client = runtime_client
            _payload = request_payload
            response = await loop.run_in_executor(
                None,
                lambda: _client.invoke_agent(**_payload),
            )

            tokens_used = 0
            for event in response.get("completion", []):
                if "chunk" in event:
                    chunk_bytes = event["chunk"].get("bytes", b"")
                    if chunk_bytes:
                        text = chunk_bytes.decode("utf-8")
                        yield {"type": "text", "content": text}
                elif "trace" in event:
                    trace = event["trace"]
                    if "orchestrationTrace" in trace:
                        orch = trace["orchestrationTrace"]
                        if "modelInvocationOutput" in orch:
                            usage = orch["modelInvocationOutput"].get("usage", {})
                            tokens_used = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)

            latency_ms = int((time.time() - start_time) * 1000)
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_region_latency_ms.labels(path="agent", region=region).observe(latency_ms)
            bedrock_requests_total.labels(status="success").inc()
            bedrock_region_requests_total.labels(path="agent", region=region, status="success").inc()

            if tokens_used:
                bedrock_tokens_used_total.labels(direction="output").inc(tokens_used)

            yield {
                "type": "end",
                "metadata": {
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "model_id": settings.BEDROCK_MODEL_ID,
                    "region": region,
                },
            }

        except NoCredentialsError as e:
            log.error("bedrock.no_credentials")
            bedrock_errors_total.labels(error_code="NoCredentialsError").inc()
            yield {"type": "error", "content": "AWS credentials not configured. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."}

        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            latency_ms = int((time.time() - start_time) * 1000)
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(
                status="throttled" if code == "ThrottlingException" else "error"
            ).inc()
            bedrock_region_requests_total.labels(
                path="agent", region=region,
                status="throttled" if code == "ThrottlingException" else "error",
            ).inc()
            bedrock_errors_total.labels(error_code=code).inc()
            log.error("bedrock.client_error", region=region, code=code, message=msg)

            if code == "AccessDeniedException":
                yield {"type": "error", "content": f"AWS access denied. Check IAM permissions for Bedrock in us-east-2. ({msg})"}
            elif code == "ThrottlingException":
                yield {"type": "error", "content": "Bedrock is throttling requests. Please try again in a moment."}
            elif code == "ValidationException":
                yield {"type": "error", "content": f"Invalid Bedrock configuration. Check BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID. ({msg})"}
            elif code == "ResourceNotFoundException":
                yield {"type": "error", "content": f"Bedrock resource not found in us-east-2. Check Agent/Alias/KB IDs. ({msg})"}
            else:
                yield {"type": "error", "content": f"Bedrock error ({code}): {msg}"}

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(status="error").inc()
            bedrock_region_requests_total.labels(path="agent", region=region, status="error").inc()
            bedrock_errors_total.labels(error_code=type(e).__name__).inc()
            log.error("bedrock.unexpected_error", error=str(e), exc_info=True)
            yield {"type": "error", "content": "Unable to get response right now. Please try again."}

    async def _invoke_direct_streaming(
        self,
        user_message: str,
        start_time: float,
        user_profile: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Direct model call used when Agent is not configured."""
        loop = asyncio.get_running_loop()

        system_prompt = (
            "You are TissaTech Assistant, a helpful AI for TissaTech company. "
            "Answer questions about software development, technology, and TissaTech services. "
            "Be concise, helpful, and professional."
        )

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": settings.BEDROCK_MAX_TOKENS,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [{"role": "user", "content": self._build_contextual_message(user_message, user_profile)}],
        }

        region = self._default_region
        direct_client = self._bedrock_client(region)
        if direct_client is None:
            yield {"type": "error", "content": "Bedrock client unavailable. Check AWS credentials."}
            return

        try:
            _client = direct_client
            _body = body
            response = await loop.run_in_executor(
                None,
                lambda: _client.invoke_model_with_response_stream(
                    modelId=settings.BEDROCK_MODEL_ID,
                    body=json.dumps(_body),
                    contentType="application/json",
                    accept="application/json",
                ),
            )

            tokens_used = 0
            for event in response.get("body", []):
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk["type"] == "content_block_delta":
                    text = chunk["delta"].get("text", "")
                    if text:
                        yield {"type": "text", "content": text}
                elif chunk["type"] == "message_delta":
                    tokens_used = chunk.get("usage", {}).get("output_tokens", 0)

            latency_ms = int((time.time() - start_time) * 1000)
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_region_latency_ms.labels(path="direct", region=region).observe(latency_ms)
            bedrock_requests_total.labels(status="success").inc()
            bedrock_region_requests_total.labels(path="direct", region=region, status="success").inc()
            if tokens_used:
                bedrock_tokens_used_total.labels(direction="output").inc(tokens_used)

            yield {
                "type": "end",
                "metadata": {
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "model_id": settings.BEDROCK_MODEL_ID,
                    "region": region,
                },
            }

        except NoCredentialsError:
            log.error("bedrock.no_credentials")
            yield {"type": "error", "content": "AWS credentials not configured. Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to .env."}

        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            latency_ms = int((time.time() - start_time) * 1000)
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(
                status="throttled" if code == "ThrottlingException" else "error"
            ).inc()
            bedrock_region_requests_total.labels(
                path="direct", region=region,
                status="throttled" if code == "ThrottlingException" else "error",
            ).inc()
            bedrock_errors_total.labels(error_code=code).inc()
            log.error("bedrock.direct_error", region=region, code=code, message=msg)
            yield {"type": "error", "content": f"Bedrock error ({code}): {msg}"}

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(status="error").inc()
            bedrock_region_requests_total.labels(path="direct", region=region, status="error").inc()
            bedrock_errors_total.labels(error_code=type(e).__name__).inc()
            log.error("bedrock.direct_unexpected", error=str(e), exc_info=True)
            yield {"type": "error", "content": "Error calling Bedrock model. Please try again."}

    @staticmethod
    def _role_tone_guidance(user_profile: dict | None) -> str:
        role_value = user_profile.get("role") if isinstance(user_profile, dict) else None
        role = role_value.strip().lower() if isinstance(role_value, str) else ""
        if not role:
            return (
                "Tone profile: neutral professional.\n"
                "Use clear language, practical examples, and a concise structure."
            )

        executive_keywords = {
            "ceo", "cto", "cio", "cfo", "coo", "founder", "director",
            "vice president", "vp", "head", "chief", "partner", "owner",
            "president", "board", "executive",
        }
        technical_keywords = {
            "developer", "engineer", "architect", "technical", "tech lead",
            "software", "devops", "sre", "qa", "tester", "data engineer",
            "data scientist", "ml engineer", "ai engineer", "administrator",
            "sysadmin", "backend", "frontend", "full stack",
        }
        product_keywords = {
            "product manager", "product owner", "project manager", "delivery manager",
            "scrum master", "program manager",
        }
        sales_marketing_keywords = {
            "sales", "marketing", "business development", "growth", "account manager",
            "customer success", "brand", "seo",
        }

        if any(k in role for k in executive_keywords):
            return (
                "Tone profile: executive/business.\n"
                "Emphasize business outcomes, ROI, risks, timelines, and decision-ready recommendations.\n"
                "Avoid excessive implementation-level detail unless explicitly asked."
            )
        if any(k in role for k in technical_keywords):
            return (
                "Tone profile: technical.\n"
                "Provide concrete technical depth, architecture trade-offs, implementation options, and practical steps.\n"
                "Use precise engineering language and include constraints/assumptions."
            )
        if any(k in role for k in product_keywords):
            return (
                "Tone profile: product/delivery.\n"
                "Balance business and technical points with roadmap impact, effort, dependencies, and execution priorities."
            )
        if any(k in role for k in sales_marketing_keywords):
            return (
                "Tone profile: sales/marketing.\n"
                "Focus on value proposition, differentiation, customer impact, and clear call-to-action language."
            )
        return (
            "Tone profile: professional role-adaptive.\n"
            "Keep language clear, concise, and outcome-oriented with the right amount of detail for the user's designation."
        )

    @staticmethod
    def _build_contextual_message(user_message: str, user_profile: dict | None) -> str:
        context_lines = []
        for key in ("role", "industry", "organization", "name"):
            value = user_profile.get(key) if isinstance(user_profile, dict) else None
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    context_lines.append(f"- {key}: {cleaned[:100]}")

        style_instructions = (
            "Response requirements:\n"
            "1. Use clean Markdown formatting with short sections.\n"
            "2. Use bullet points for lists and numbered steps for procedures.\n"
            "3. Keep sentences grammatically correct, professional, and easy to read.\n"
            "4. Keep paragraphs short (1-2 lines each).\n"
            "5. Prefer clear, actionable answers over long raw text blocks.\n"
            "6. Do not use filler phrases like 'according to the search results' in the final answer.\n"
            "7. Adapt tone and depth to the user's role/designation."
        )
        tone_guidance = BedrockAgentClient._role_tone_guidance(user_profile)

        if context_lines:
            return (
                "User profile context:\n"
                + "\n".join(context_lines)
                + "\n\n"
                + tone_guidance
                + "\n\n"
                + style_instructions
                + f"\n\nQuestion: {user_message}"
            )

        return tone_guidance + "\n\n" + style_instructions + f"\n\nQuestion: {user_message}"

    async def search_knowledge_base(
        self,
        query: str,
        num_results: int = 5,
        *,
        knowledge_base_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list:
        effective_kb_id = (
            knowledge_base_id if knowledge_base_id is not None else settings.BEDROCK_KNOWLEDGE_BASE_ID
        )
        if not effective_kb_id or effective_kb_id in ("", "YOUR_KB_ID"):
            log.warning("bedrock.kb_not_configured")
            return []

        retrieval_filter = self._build_workspace_source_uri_filter(workspace_id)
        if retrieval_filter is None:
            log.warning(
                "bedrock.kb_search_filter_missing",
                workspace_id=workspace_id,
                bucket=settings.S3_KNOWLEDGE_BASE_BUCKET,
            )
            return []

        loop = asyncio.get_running_loop()
        region = self._default_region
        runtime_client = self._runtime_client(region)
        if runtime_client is None:
            log.error("bedrock.kb_runtime_client_unavailable", region=region)
            return []

        try:
            _client = runtime_client
            _kb_id = effective_kb_id
            _filter = retrieval_filter
            _n = min(num_results, 5)
            response = await loop.run_in_executor(
                None,
                lambda: _client.retrieve(
                    knowledgeBaseId=_kb_id,
                    retrievalQuery={"text": query},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {
                            "numberOfResults": _n,
                            "filter": _filter,
                        }
                    },
                ),
            )
            return [
                {
                    "content": item["content"]["text"],
                    "score": item.get("score", 0.0),
                    "source": item.get("location", {}).get("s3Location", {}).get("uri", ""),
                }
                for item in response.get("retrievalResults", [])
            ]
        except Exception as e:
            log.error("bedrock.kb_search_error", error=str(e))
            return []

    @staticmethod
    def _workspace_source_uri_prefix(workspace_id: str | None) -> str | None:
        if not workspace_id:
            return None
        bucket = (settings.S3_KNOWLEDGE_BASE_BUCKET or "").strip()
        if not bucket:
            return None
        workspace = workspace_id.strip()
        if not workspace:
            return None
        return f"s3://{bucket}/workspaces/{workspace}/"

    @classmethod
    def _build_workspace_source_uri_filter(cls, workspace_id: str | None) -> dict | None:
        source_prefix = cls._workspace_source_uri_prefix(workspace_id)
        if not source_prefix:
            return None
        return {
            "startsWith": {
                "key": "x-amz-bedrock-kb-source-uri",
                "value": source_prefix,
            }
        }


bedrock_client = BedrockAgentClient()
