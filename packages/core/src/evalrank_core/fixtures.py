from __future__ import annotations

from evalrank_core.contracts import (
    CapabilityFingerprintInput,
    ProblemDetails,
    RawEntry,
    UseCase,
    UseCaseCatalog,
)
from evalrank_core.canonical_json import sha256_hex
from evalrank_core.decision_contracts import (
    ConfigurationPassportV1,
    EvaluatedConfigurationV1,
    IntervalUncertaintyV1,
    ObservationV1,
    ProportionMetricV1,
    RunInputArtifactV1,
    RunProvenanceV1,
)


PUBLIC_GENERATED_AT = "2026-06-25T00:00:00Z"
PUBLIC_CATALOG_METHODOLOGY_VERSION = "2026-08-04.1.catalog-manifest-v1"
PUBLIC_CATALOG_GENERATED_AT = "2026-08-04T00:00:00Z"
PUBLIC_USE_CASE_ID = "web-browsing"
PUBLIC_FIXTURE_KINDS = (
    "fingerprint",
    "observation",
    "problem",
    "raw-entry",
    "use-cases",
)


_USE_CASE_ROWS = (
    ("coding-general", "Coding (general)", "Rank coding models and agents on general software tasks: code generation, repository-level SWE, and terminal work", ("model", "tool", "agent")),
    (
        "function-calling",
        "Function and tool calling",
        "Emit correct schema-valid tool calls",
        ("model", "tool", "agent"),
    ),
    ("mcp-tool-orchestration", "MCP tool orchestration", "Coordinate MCP tools to complete a task", ("model", "tool", "agent")),
    ("web-browsing", "Web browsing and navigation", "Retrieve and act on live web content", ("model", "tool", "agent")),
    ("computer-use", "Computer use", "Operate a graphical interface to complete a task", ("model", "agent")),
    ("deep-research", "Deep research", "Synthesize multiple sources with traceable citations", ("model", "tool", "agent")),
    ("customer-support", "Customer support agent", "Resolve user support issues end to end", ("model", "agent")),
    ("enterprise-crm-workflow", "Enterprise and CRM workflow", "Execute business workflows across enterprise systems", ("tool", "agent")),
    ("math-reasoning", "Mathematical reasoning", "Solve quantitative or symbolic problems", ("model",)),
    ("general-knowledge-qa", "General knowledge QA", "Answer broad knowledge questions accurately", ("model", "tool")),
    ("rag-retrieval", "RAG and retrieval", "Retrieve relevant context and ground an answer", ("model", "tool")),
    ("long-term-memory", "Long-term memory", "Persist and recall useful information across sessions", ("model", "tool", "agent")),
    ("finance", "Finance", "Perform domain-grounded financial reasoning and workflows", ("model", "tool", "agent")),
    ("legal", "Legal", "Perform domain-grounded legal reasoning and drafting", ("model", "tool", "agent")),
    ("medical", "Medical", "Perform domain-grounded clinical reasoning and question answering", ("model", "tool", "agent")),
    ("multilingual", "Multilingual", "Maintain quality across languages and translation tasks", ("model", "tool", "agent")),
    ("vision-multimodal", "Vision and multimodal", "Reason over images, audio, or video", ("model", "agent")),
    ("coding-frontend", "Coding (frontend)", "Rank models and agents on building and iterating web interfaces from a specification", ("model", "agent")),
    ("sre-incident-response", "SRE incident response", "Diagnose and repair live service or infrastructure incidents", ("agent",)),
    ("reasoning", "Reasoning", "Solve novel multi-step reasoning tasks", ("model",)),
    ("factuality", "Factuality", "Produce correct and grounded factual claims", ("model", "tool")),
    (
        "professional-deliverable-creation",
        "Professional deliverables",
        "Create review-ready professional work products from a complete brief, domain context, and reference files.",
        ("model", "agent"),
    ),
    (
        "computational-research-reproduction",
        "Computational research reproduction",
        "Reproduce published computational results by implementing or executing experiments from papers, code, data, and environments.",
        ("agent",),
    ),
)


def sample_capability_fingerprint_input() -> CapabilityFingerprintInput:
    return CapabilityFingerprintInput(
        id_scheme="reverse_dns",
        canonical_id="io.evalrank.public-search-demo",
        entity_kind="mcp_server",
        declared_capability_shape={
            "tool_names": ["search"],
            "param_schemas": {"search": {"type": "object"}},
            "declared_scopes": ["web.search"],
            "commit_sha": "abc123",
        },
    )


def sample_raw_entry() -> RawEntry:
    return RawEntry(
        source="public-fixture",
        source_id="public-fixture:search-demo:2026-06-25",
        entity_kind="mcp_server",
        canonical_id="io.evalrank.public-search-demo",
        raw_metadata={
            "display_name": "Public Search Demo",
            "homepage": "https://example.com/evalrank/public-search-demo",
        },
        declared_capability_shape={
            "tool_names": ["search"],
            "param_schemas": {"search": {"type": "object"}},
        },
        fetched_at=PUBLIC_GENERATED_AT,
    )


def sample_use_case_catalog() -> UseCaseCatalog:
    use_cases = tuple(
        UseCase(
            id=use_case_id,
            name=name,
            definition=definition,
            entity_kinds=entity_kinds,
        )
        for use_case_id, name, definition, entity_kinds in _USE_CASE_ROWS
    )
    return UseCaseCatalog(
        methodology_version=PUBLIC_CATALOG_METHODOLOGY_VERSION,
        generated_at=PUBLIC_CATALOG_GENERATED_AT,
        use_cases=use_cases,
    )


def sample_problem_details() -> ProblemDetails:
    return ProblemDetails(
        type="https://evalrank.ai/problems/validation",
        title="Validation failed",
        status=422,
        detail="request_id is required",
        code="validation",
        retriable=False,
        field="request_id",
        request_id="req_public_fixture_01",
        doc_url="https://evalrank.ai/docs/errors#validation",
    )


def _sample_configuration_passport() -> ConfigurationPassportV1:
    return ConfigurationPassportV1(
        entity_kind="component_configuration",
        canonical_name="io.evalrank.public-search-demo",
        revision="2026-06-25",
        interaction_policy="retrieval",
        configuration_passport_class="component-configuration-v1",
        harness=None,
        scaffold=None,
        tools=("search",),
        quantization=None,
        system_prompt_policy=None,
        environment=None,
    )


def _sample_evaluated_configuration() -> EvaluatedConfigurationV1:
    passport = _sample_configuration_passport()
    return EvaluatedConfigurationV1(
        evaluated_configuration_id=f"config_{sha256_hex(passport.to_dict())}",
        passport=passport,
    )


def sample_observation() -> ObservationV1:
    return ObservationV1(
        observation_id="obs_public_demo_01",
        evaluated_configuration_id=_sample_evaluated_configuration().evaluated_configuration_id,
        metric=ProportionMetricV1(value="0.875", numerator=35, denominator=40),
        uncertainty=IntervalUncertaintyV1(
            low="0.8",
            high="0.88",
            confidence_level="0.95",
            method="reported",
        ),
        provenance=RunProvenanceV1(
            run_id="run_public_demo_01",
            benchmark_family_id="public-search-freshness",
            feed_id="public-search-freshness-official",
            source_artifacts=(
                RunInputArtifactV1(
                    role="primary",
                    source_artifact_id=f"artifact_{'a' * 64}",
                ),
            ),
            parser_id="public-fixture-parser",
            parser_version="1",
            started_at="2026-06-25T00:00:00Z",
            completed_at="2026-06-25T00:00:01Z",
            harness_version="2026-06-25.1",
        ),
    )


def sample_public_fixture(kind: str) -> dict:
    if kind == "fingerprint":
        return sample_capability_fingerprint_input().to_dict()
    if kind == "observation":
        return sample_observation().to_dict()
    if kind == "problem":
        return sample_problem_details().to_dict()
    if kind == "raw-entry":
        return sample_raw_entry().to_dict()
    if kind == "use-cases":
        return sample_use_case_catalog().to_dict()
    raise ValueError(f"fixture kind must be one of: {', '.join(PUBLIC_FIXTURE_KINDS)}")
