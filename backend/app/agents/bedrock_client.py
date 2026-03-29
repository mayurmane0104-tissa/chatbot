"""
app/agents/bedrock_client.py  — FIXED VERSION
Key fixes:
1. Falls back to direct Claude model if Agent ID not configured
2. Better error messages with actual exception details logged
3. Handles ThrottlingException, AccessDeniedException, ValidationException
4. Test mode: if BEDROCK_AGENT_ID is empty, uses direct model invocation
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
)

log = structlog.get_logger()


class BedrockAgentClient:

    def __init__(self):
        boto_config = Config(
            region_name=settings.AWS_REGION,
            retries={"max_attempts": 2, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=120,
        )

        credentials = {}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
            credentials["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
            credentials["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()

        try:
            self._runtime = boto3.client("bedrock-agent-runtime", config=boto_config, **credentials)
            self._bedrock = boto3.client("bedrock-runtime", config=boto_config, **credentials)
            log.info("bedrock.client_initialized", region=settings.AWS_REGION)
        except Exception as e:
            log.error("bedrock.client_init_failed", error=str(e))
            self._runtime = None
            self._bedrock = None

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
    ) -> AsyncGenerator[dict, None]:
        """
        Stream response from Bedrock Agent.
        Falls back to direct model call if Agent ID is not configured.
        """
        start_time = time.time()
        status = "success"
        error_code = None

        # By default, do NOT use global shared agent IDs to avoid cross-tenant leakage.
        effective_agent_id = agent_id
        effective_agent_alias_id = agent_alias_id
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
            async for chunk in self._invoke_direct_streaming(user_message, start_time, user_profile=user_profile):
                yield chunk
            return

        loop = asyncio.get_event_loop()
        enriched_message = self._build_contextual_message(user_message, user_profile)

        try:
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
                                    "numberOfResults": 15,
                                    "filter": retrieval_filter,
                                }
                            },
                        }
                    ]
                }

            response = await loop.run_in_executor(
                None,
                lambda: self._runtime.invoke_agent(**request_payload),
            )

            full_text = ""
            tokens_used = 0

            for event in response.get("completion", []):
                if "chunk" in event:
                    chunk_bytes = event["chunk"].get("bytes", b"")
                    if chunk_bytes:
                        text = chunk_bytes.decode("utf-8")
                        full_text += text
                        yield {"type": "text", "content": text}

                elif "trace" in event:
                    trace = event["trace"]
                    if "orchestrationTrace" in trace:
                        orch = trace["orchestrationTrace"]
                        if "modelInvocationOutput" in orch:
                            usage = orch["modelInvocationOutput"].get("usage", {})
                            tokens_used = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)

            # latency_ms = int((time.time() - start_time) * 1000)
            # yield {"type": "end", "metadata": {"tokens_used": tokens_used, "latency_ms": latency_ms, "model_id": settings.BEDROCK_MODEL_ID}}
            latency_ms = int((time.time() - start_time) * 1000)

            # Metrics
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(status="success").inc()

            if tokens_used:
                bedrock_tokens_used_total.labels(direction="output").inc(tokens_used)

            yield {
                "type": "end",
                "metadata": {
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "model_id": settings.BEDROCK_MODEL_ID,
                },
            }

        except NoCredentialsError:
            log.error("bedrock.no_credentials")
            yield {"type": "error", "content": "AWS credentials not configured. Please check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file."}

        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            # log.error("bedrock.client_error", code=code, message=msg)
            latency_ms = int((time.time() - start_time) * 1000)

            # Metrics
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(
                status="throttled" if code == "ThrottlingException" else "error"
            ).inc()
            bedrock_errors_total.labels(error_code=code).inc()

            log.error("bedrock.client_error", code=code, message=msg)

            if code == "AccessDeniedException":
                yield {"type": "error", "content": f"AWS access denied. Check your IAM permissions for Bedrock. ({msg})"}
            elif code == "ThrottlingException":
                yield {"type": "error", "content": "Bedrock is throttling requests. Please try again in a moment."}
            elif code == "ValidationException":
                yield {"type": "error", "content": f"Invalid Bedrock configuration. Check your BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID. ({msg})"}
            elif code == "ResourceNotFoundException":
                yield {"type": "error", "content": f"Bedrock resource not found. Check your Agent ID, Alias ID, and Knowledge Base ID. ({msg})"}
            else:
                yield {"type": "error", "content": f"Bedrock error ({code}): {msg}"}

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            # Metrics
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(status="error").inc()
            bedrock_errors_total.labels(error_code=type(e).__name__).inc()

            log.error("bedrock.unexpected_error", error=str(e), exc_info=True)
            # yield {"type": "error", "content": f"Unexpected error: {str(e)[:200]}"}

    async def _invoke_direct_streaming(
        self,
        user_message: str,
        start_time: float,
        user_profile: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Direct model call — used when Agent is not configured."""
        loop = asyncio.get_event_loop()

        system_prompt = (
            "You are TissaTech Assistant, a helpful AI for TissaTech company. "
            "Answer questions about software development, technology, and TissaTech services. "
            "Be concise, helpful, and professional."
        )

        start_time = start_time

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": settings.BEDROCK_MAX_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": self._build_contextual_message(user_message, user_profile)}],
        }

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._bedrock.invoke_model_with_response_stream(
                    modelId=settings.BEDROCK_MODEL_ID,
                    body=json.dumps(body),
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

            # latency_ms = int((time.time() - start_time) * 1000)
            # yield {"type": "end", "metadata": {"tokens_used": tokens_used, "latency_ms": latency_ms, "model_id": settings.BEDROCK_MODEL_ID}}
            latency_ms = int((time.time() - start_time) * 1000)

            # Metrics
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(status="success").inc()

            if tokens_used:
                bedrock_tokens_used_total.labels(direction="output").inc(tokens_used)

            yield {
                "type": "end",
                "metadata": {
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "model_id": settings.BEDROCK_MODEL_ID,
                },
            }

        except NoCredentialsError:
            yield {"type": "error", "content": "AWS credentials not configured. Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to your .env file."}
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]

            latency_ms = int((time.time() - start_time) * 1000)

            # Metrics
            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(
                status="throttled" if code == "ThrottlingException" else "error"
            ).inc()
            bedrock_errors_total.labels(error_code=code).inc()

            log.error("bedrock.direct_error", code=code, message=msg)
            yield {"type": "error", "content": f"Bedrock error ({code}): {msg}"}
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            bedrock_response_latency_ms.observe(latency_ms)
            bedrock_requests_total.labels(status="error").inc()
            bedrock_errors_total.labels(error_code=type(e).__name__).inc()

            log.error("bedrock.direct_unexpected", error=str(e), exc_info=True)
            # yield {"type": "error", "content": f"Error calling Bedrock: {str(e)[:200]}"}

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
        num_results: int = 15,
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

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._runtime.retrieve(
                    knowledgeBaseId=effective_kb_id,
                    retrievalQuery={"text": query},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {
                            "numberOfResults": num_results,
                            "filter": retrieval_filter,
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
