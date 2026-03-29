"""
app/workers/bedrock_provisioner.py
Synchronous Bedrock provisioning — called from Celery tasks (no asyncio).

Auto-creates per-workspace AWS resources:
  1. Bedrock Knowledge Base (OpenSearch Serverless managed vector store)
  2. S3 Data Source linked to workspaces/{workspace_id}/ prefix
  3. Bedrock Agent configured with the workspace's KB
  4. Agent Alias

All functions are synchronous (boto3 is synchronous by default).
"""
import time

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

log = structlog.get_logger()

_AGENT_PREPARE_POLL_INTERVAL = 5
_AGENT_PREPARE_TIMEOUT = 180


def _client(service: str):
    """Create a boto3 client with credentials from settings."""
    creds = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
        creds["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
        creds["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
    return boto3.client(
        service,
        region_name=settings.AWS_REGION,
        config=Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=15,
            read_timeout=60,
        ),
        **creds,
    )


def provision_workspace_bedrock(workspace_id: str, workspace_slug: str) -> dict:
    """
    Idempotently provision all Bedrock resources for one workspace.

    Returns:
        {
            "bedrock_kb_id": str,
            "bedrock_kb_ds_id": str,
            "bedrock_agent_id": str,
            "bedrock_agent_alias_id": str,
        }

    Raises RuntimeError if required .env settings are missing.
    """
    if not settings.S3_KNOWLEDGE_BASE_BUCKET:
        raise RuntimeError(
            "S3_KNOWLEDGE_BASE_BUCKET is not configured in .env. "
            "Set it to your S3 bucket name (e.g. tissatech-kb-data)."
        )
    if not settings.BEDROCK_AGENT_ROLE_ARN:
        raise RuntimeError(
            "BEDROCK_AGENT_ROLE_ARN is not configured in .env. "
            "Create an IAM role trusted by bedrock.amazonaws.com with "
            "AmazonBedrockFullAccess + S3 read, then set the ARN."
        )
    if not settings.BEDROCK_OPENSEARCH_COLLECTION_ARN:
        raise RuntimeError(
            "BEDROCK_OPENSEARCH_COLLECTION_ARN is not configured in .env. "
            "Set it to your OpenSearch Serverless collection ARN used for Bedrock KB storage."
        )

    bedrock = _client("bedrock-agent")
    bucket = settings.S3_KNOWLEDGE_BASE_BUCKET
    prefix = f"workspaces/{workspace_id}/"
    role_arn = settings.BEDROCK_AGENT_ROLE_ARN
    short_id = workspace_id[:8]

    # ── 1. Create Knowledge Base ──────────────────────────────────────────────
    kb_name = f"tt-kb-{workspace_slug[:20]}-{short_id}"
    log.info("provisioner.creating_kb", name=kb_name, workspace_id=workspace_id)

    kb_id = _find_existing_kb(bedrock, kb_name)
    if not kb_id:
        try:
            resp = bedrock.create_knowledge_base(
                name=kb_name,
                description=f"TissaTech KB for {workspace_slug}",
                roleArn=role_arn,
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": (
                            f"arn:aws:bedrock:{settings.AWS_REGION}::foundation-model/"
                            f"{settings.BEDROCK_EMBEDDING_MODEL_ID}"
                        ),
                    },
                },
                storageConfiguration={
                    "type": "OPENSEARCH_SERVERLESS",
                    "opensearchServerlessConfiguration": {
                        "collectionArn": settings.BEDROCK_OPENSEARCH_COLLECTION_ARN,
                        "vectorIndexName": f"idx-{short_id}",
                        "fieldMapping": {
                            "vectorField": "embedding",
                            "textField": "text",
                            "metadataField": "metadata",
                        },
                    },
                },
            )
            kb_id = resp["knowledgeBase"]["knowledgeBaseId"]
        except ClientError as e:
            if "ConflictException" in str(e):
                kb_id = _find_existing_kb(bedrock, kb_name)
                if not kb_id:
                    raise RuntimeError(f"KB conflict but could not locate existing KB '{kb_name}'")
            else:
                raise

    log.info("provisioner.kb_ready", kb_id=kb_id)
    _wait_for_kb_active(bedrock, kb_id)

    # ── 2. Create S3 Data Source ──────────────────────────────────────────────
    ds_name = f"tt-ds-{workspace_slug[:20]}-{short_id}"
    log.info("provisioner.creating_data_source", name=ds_name, bucket=bucket, prefix=prefix)

    ds_id = _find_existing_ds(bedrock, kb_id, ds_name)
    if not ds_id:
        try:
            resp = bedrock.create_data_source(
                knowledgeBaseId=kb_id,
                name=ds_name,
                description=f"S3 source for {workspace_slug}",
                dataSourceConfiguration={
                    "type": "S3",
                    "s3Configuration": {
                        "bucketArn": f"arn:aws:s3:::{bucket}",
                        "inclusionPrefixes": [prefix],
                    },
                },
                vectorIngestionConfiguration={
                    "chunkingConfiguration": {
                        "chunkingStrategy": "FIXED_SIZE",
                        "fixedSizeChunkingConfiguration": {
                            "maxTokens": 512,
                            "overlapPercentage": 20,
                        },
                    },
                },
            )
            ds_id = resp["dataSource"]["dataSourceId"]
        except ClientError as e:
            if "ConflictException" in str(e):
                ds_id = _find_existing_ds(bedrock, kb_id, ds_name)
                if not ds_id:
                    raise RuntimeError(f"DS conflict but could not locate existing DS '{ds_name}'")
            else:
                raise

    log.info("provisioner.data_source_ready", ds_id=ds_id)

    # ── 3. Create Agent ───────────────────────────────────────────────────────
    agent_name = f"tt-agent-{workspace_slug[:18]}-{short_id}"
    instruction = (
        f"You are an AI assistant for {workspace_slug}. "
        "Answer questions accurately using only the information in your knowledge base. "
        "If the answer is not in the knowledge base, say so — never invent information. "
        "Be concise, helpful, and professional."
    )
    log.info("provisioner.creating_agent", name=agent_name, workspace_id=workspace_id)

    agent_id = _find_existing_agent(bedrock, agent_name)
    if not agent_id:
        try:
            resp = bedrock.create_agent(
                agentName=agent_name,
                description=f"TissaTech assistant for {workspace_slug}",
                agentResourceRoleArn=role_arn,
                foundationModel=settings.BEDROCK_MODEL_ID,
                instruction=instruction,
                idleSessionTTLInSeconds=1800,
            )
            agent_id = resp["agent"]["agentId"]
        except ClientError as e:
            if "ConflictException" in str(e):
                agent_id = _find_existing_agent(bedrock, agent_name)
                if not agent_id:
                    raise RuntimeError(f"Agent conflict but could not locate '{agent_name}'")
            else:
                raise

    log.info("provisioner.agent_created", agent_id=agent_id)

    # ── 4. Associate KB with Agent ────────────────────────────────────────────
    try:
        bedrock.associate_agent_knowledge_base(
            agentId=agent_id,
            agentVersion="DRAFT",
            knowledgeBaseId=kb_id,
            description=f"KB for {workspace_slug}",
            knowledgeBaseState="ENABLED",
        )
        log.info("provisioner.kb_associated", agent_id=agent_id, kb_id=kb_id)
    except ClientError as e:
        if "ConflictException" not in str(e):
            raise

    # ── 5. Prepare Agent ──────────────────────────────────────────────────────
    log.info("provisioner.preparing_agent", agent_id=agent_id)
    bedrock.prepare_agent(agentId=agent_id)
    _wait_for_agent_prepared(bedrock, agent_id)

    # ── 6. Create Alias ───────────────────────────────────────────────────────
    alias_name = "production"
    agent_alias_id = _find_existing_alias(bedrock, agent_id, alias_name)
    if not agent_alias_id:
        try:
            resp = bedrock.create_agent_alias(
                agentId=agent_id,
                agentAliasName=alias_name,
                description="Production alias",
            )
            agent_alias_id = resp["agentAlias"]["agentAliasId"]
        except ClientError as e:
            if "ConflictException" in str(e):
                agent_alias_id = _find_existing_alias(bedrock, agent_id, alias_name)
                if not agent_alias_id:
                    raise RuntimeError(f"Alias conflict but could not locate '{alias_name}'")
            else:
                raise

    log.info(
        "provisioner.complete",
        workspace_id=workspace_id,
        kb_id=kb_id, ds_id=ds_id,
        agent_id=agent_id, alias_id=agent_alias_id,
    )

    return {
        "bedrock_kb_id": kb_id,
        "bedrock_kb_ds_id": ds_id,
        "bedrock_agent_id": agent_id,
        "bedrock_agent_alias_id": agent_alias_id,
    }


def start_kb_ingestion(kb_id: str, ds_id: str) -> str:
    """Start ingestion job. Returns job ID."""
    bedrock = _client("bedrock-agent")
    resp = bedrock.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
        description="TissaTech automated ingestion",
    )
    job_id = resp["ingestionJob"]["ingestionJobId"]
    log.info("ingestion.started", kb_id=kb_id, ds_id=ds_id, job_id=job_id)
    return job_id


def wait_for_ingestion_complete(kb_id: str, ds_id: str, job_id: str, timeout: int = 600) -> str:
    """
    Poll ingestion job every 10s until COMPLETE/FAILED/STOPPED.
    Returns final status string. Raises TimeoutError after `timeout` seconds.
    """
    bedrock = _client("bedrock-agent")
    deadline = time.time() + timeout

    while True:
        resp = bedrock.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            ingestionJobId=job_id,
        )
        status = resp["ingestionJob"]["status"]
        stats  = resp["ingestionJob"].get("statistics", {})
        log.info("ingestion.poll", status=status, stats=stats, job_id=job_id)

        if status in ("COMPLETE", "FAILED", "STOPPED"):
            return status

        if time.time() > deadline:
            raise TimeoutError(f"Ingestion job {job_id} timed out after {timeout}s")

        time.sleep(10)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_existing_kb(client, name: str):
    try:
        resp = client.list_knowledge_bases(maxResults=100)
        for kb in resp.get("knowledgeBaseSummaries", []):
            if kb.get("name") == name:
                return kb["knowledgeBaseId"]
    except Exception:
        pass
    return None


def _find_existing_ds(client, kb_id: str, name: str):
    try:
        resp = client.list_data_sources(knowledgeBaseId=kb_id, maxResults=100)
        for ds in resp.get("dataSourceSummaries", []):
            if ds.get("name") == name:
                return ds["dataSourceId"]
    except Exception:
        pass
    return None


def _find_existing_agent(client, name: str):
    try:
        resp = client.list_agents(maxResults=100)
        for a in resp.get("agentSummaries", []):
            if a.get("agentName") == name:
                return a["agentId"]
    except Exception:
        pass
    return None


def _find_existing_alias(client, agent_id: str, name: str):
    try:
        resp = client.list_agent_aliases(agentId=agent_id, maxResults=100)
        for a in resp.get("agentAliasSummaries", []):
            if a.get("agentAliasName") == name:
                return a["agentAliasId"]
    except Exception:
        pass
    return None


def _wait_for_kb_active(client, kb_id: str, timeout: int = 120):
    deadline = time.time() + timeout
    while True:
        resp = client.get_knowledge_base(knowledgeBaseId=kb_id)
        status = resp["knowledgeBase"]["status"]
        if status == "ACTIVE":
            return
        if status in ("FAILED", "DELETE_UNSUCCESSFUL"):
            raise RuntimeError(f"KB {kb_id} failed to activate. Status: {status}")
        if time.time() > deadline:
            raise TimeoutError(f"KB {kb_id} did not become ACTIVE within {timeout}s")
        time.sleep(5)


def _wait_for_agent_prepared(client, agent_id: str, timeout: int = _AGENT_PREPARE_TIMEOUT):
    deadline = time.time() + timeout
    while True:
        resp = client.get_agent(agentId=agent_id)
        status = resp["agent"]["agentStatus"]
        if status == "PREPARED":
            return
        if status == "FAILED":
            raise RuntimeError(f"Agent {agent_id} failed to prepare.")
        if time.time() > deadline:
            raise TimeoutError(f"Agent {agent_id} did not PREPARE within {timeout}s")
        time.sleep(_AGENT_PREPARE_POLL_INTERVAL)
