"""Typed schemas for every piece of durable project state.

One source of truth: these pydantic models validate the YAML/JSON files in the
repo AND generate the JSON Schemas passed to `claude -p --json-schema`, so the
orchestrator and the agents can never disagree about a format.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Risk = Literal["low", "medium", "high", "critical"]
Comparator = Literal[">=", ">", "<=", "<"]
Role = Literal["planner", "builder", "scientist", "critic", "scout", "scribe", "none"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- objectives
class Hypothesis(_Strict):
    statement: str
    null_hypothesis: str = ""
    why_it_matters: str = ""
    decision_if_pass: str = ""
    decision_if_fail: str = ""
    decision_if_inconclusive: str = ""  # quoted to the founder on an INCONCLUSIVE verdict (audit 2026-10-19)


class Uncertainty(_Strict):
    # "ci": judge on the conservative CI bound; "point": judge on the point value.
    use: Literal["ci", "point"] = "ci"


class Criterion(_Strict):
    id: str
    metric: str  # "E002.spearman_rho_Lloop"
    comparator: Comparator
    threshold: float
    uncertainty: Uncertainty = Uncertainty()
    description: str = ""


class Acceptance(_Strict):
    required_experiments: list[str]
    pass_all: list[Criterion]  # every one must be definitely satisfied -> PASS
    fail_any: list[Criterion] = []  # any one definitely satisfied -> FAIL
    max_evaluations: int = 3  # forking-paths guard


class FailureMode(_Strict):
    id: str
    description: str
    detection: str = ""
    response: str = ""


class Budget(_Strict):
    usd: float = 50.0
    cpu_hours: float = 20.0
    wall_days: float = 14.0


class Objective(_Strict):
    """Founder-owned. Frozen (criteria_hash) once approved."""

    id: str
    title: str
    kind: Literal["hypothesis", "build", "investigation", "decision"] = "hypothesis"
    priority: int = 2  # 1 = highest
    risk: Risk = "high"
    depends_on: list[str] = []
    unlocks: list[str] = []
    hypothesis: Hypothesis
    scope_in: list[str] = []
    scope_out: list[str] = []
    evidence_plan: list[str] = []  # experiment ids
    acceptance: Acceptance
    failure_modes: list[FailureMode] = []
    budget: Budget = Budget()
    require_plan_approval: bool = True
    notes: str = ""


class ObjectiveState(_Strict):
    """Orchestrator-owned mutable state, kept apart from the frozen objective."""

    status: Literal[
        "draft", "active", "blocked", "evaluating", "passed", "failed",
        "inconclusive", "needs_founder", "abandoned", "superseded",
    ] = "draft"
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    criteria_hash: Optional[str] = None
    evaluations: list[str] = []  # evaluation ids
    last_verdict: Optional[str] = None
    evaluated_runs: dict[str, str] = {}  # experiment id -> run id used by the last evaluation
    pending_evaluation: Optional[str] = None  # evaluation id awaiting critic review
    pending_review_ref: Optional[str] = None  # commit the pending evaluation's critics review (snapshot binding)
    replans: int = 0
    max_replans: int = 3
    needs_replan: bool = True
    spent_usd: float = 0.0
    budget_override_usd: Optional[float] = None
    log: list[str] = []
    # Evidence rules (audit 2026-10-19): objectives approved by evaluator >= 2.0.0 record 2; O000/O001 keep 1.
    evidence_rules: int = 1
    # Hash of hypothesis, scope, evidence plan and acceptance at approval (criteria_hash covers acceptance only).
    frozen_hash: Optional[str] = None


# --------------------------------------------------------------------------- tasks
TaskType = Literal[
    "implement", "experiment", "investigate", "design_experiment",
    "research", "review", "docs", "plan",
]
TaskStatus = Literal[
    "proposed", "todo", "running", "verify", "review", "merge",
    "done", "failed", "cancelled", "needs_founder",
]


class DoDCheck(_Strict):
    cmd: Optional[str] = None  # must exit 0
    exists: Optional[str] = None  # path must exist
    timeout_s: int = 900


class Task(_Strict):
    id: str
    objective: str
    title: str
    type: TaskType
    agent: Role = "builder"
    status: TaskStatus = "todo"
    depends_on: list[str] = []
    description: str = ""
    context_files: list[str] = []
    deliverables: list[str] = []
    touches: list[str] = []  # globs, used to avoid concurrent edits
    definition_of_done: list[DoDCheck] = []
    experiment: Optional[str] = None
    risk: Risk = "low"
    model: Optional[str] = None
    budget_usd: float = 3.0
    max_turns: int = 80
    wall_minutes: Optional[int] = None  # this task's run wall-clock limit; None = policy limits.run_wall_minutes
    attempts: int = 0
    max_attempts: int = 3
    branch: Optional[str] = None
    pr: Optional[int] = None
    runs: list[str] = []
    created_by: str = "planner"
    created_at: Optional[str] = None
    protected_approved: bool = False  # set only by a founder inbox approval
    approval: Optional[str] = None  # inbox id of that approval (recorded as a commit trailer)
    target: Optional[str] = None  # review tasks: the task id or evaluation id under review
    lens: Optional[str] = None  # review tasks: physics | numerics | statistics | software | general
    trigger: Optional[str] = None  # plan tasks: why the planner was invoked
    rationale: str = ""  # never shown to reviewers
    history: list[dict[str, Any]] = []


# --------------------------------------------------------------------------- experiments
class MetricSpec(_Strict):
    name: str
    description: str = ""
    unit: str = ""


class SanitySpec(_Strict):
    name: str
    description: str = ""


class CodeMatch(_Strict):
    """This experiment's hash of ``path`` must equal the hash recorded for it in the evidence of ``objective``'s
    last PASS evaluation (e.g. the judge of O003 must be the L2 code that O004 validated)."""

    path: str
    objective: str


class RowsSpec(_Strict):
    """The run's flat-records artifact ({"schema": "mfos.rows/1", "rows": [...]}) written with ExperimentRun.rows."""

    artifact: str = "rows.json"


class CISpec(_Strict):
    scheme: Literal["plain", "stratified", "cluster"] = "plain"
    n_boot: int = 2000
    level: float = 0.95
    seed: int = 0
    strata: list[str] = []  # columns, for scheme "stratified"
    cluster: Optional[str] = None  # column, for scheme "cluster"


class RecomputeSpec(_Strict):
    """How the evaluator recomputes one reported metric from the rows (mfos.metrics.METRICS[fn])."""

    metric: str  # the metric name the runner reports, e.g. spearman_rho_Lloop
    fn: str
    pred: Optional[str] = None  # column of the model under test
    ref: Optional[str] = None  # column of the reference
    strata: list[str] = []  # columns whose values define strata
    group: Optional[str] = None
    role: Optional[str] = None
    params: dict[str, Any] = {}  # e.g. {k_frac: 0.1, within_frac: 0.2}, {q: 0.95}, {agg: median}
    where: dict[str, Any] = {}  # only rows whose columns equal these values
    ci: Optional[CISpec] = None
    rel_tol: float = 1e-9
    abs_tol: float = 1e-12


class NullSpec(_Strict):
    """A predictor that ignores the decision-relevant information. A pass criterion that it also satisfies does not
    discriminate (verdict non_discriminating)."""

    name: str
    kind: Literal["stratum_mean", "column"]
    strata: list[str] = []  # stratum_mean: the mean of the metric's ref column within these strata
    column: Optional[str] = None  # column: a predictor the runner wrote into the rows
    applies_to: list[str] = []  # metric names


class ExperimentSpec(_Strict):
    id: str
    title: str
    objective: str
    status: Literal["draft", "registered", "retired"] = "draft"
    runner: str  # shell command, run from repo root of a clean checkout
    config: dict[str, Any] = {}
    sealed_seed: bool = False  # orchestrator injects an unseen seed per run
    metrics: list[MetricSpec]
    sanity_checks: list[SanitySpec] = []
    timeout_min: int = 120
    cpu_hours_est: float = 1.0
    registered_by: Optional[str] = None
    registered_at: Optional[str] = None
    spec_hash: Optional[str] = None
    # repo path -> sha256 of each file the runner command names, frozen at registration (covered by spec_hash)
    runner_files: dict[str, str] = {}
    # ---- evidence rules v2 (audit 2026-10-19). Each field enters spec_hash only when it differs from its default
    # (Store.spec_hash), so specs registered before these fields existed keep their recorded hashes.
    evidence_rules: int = 1  # set to 2 by `mfos exp register`; v2 checks apply only to specs with 2
    code_under_test: list[str] = []  # repo files or globs whose sha256 every run records (provenance.code)
    code_must_match: list[CodeMatch] = []
    requires_passed: list[str] = []  # objectives that must have passed before this experiment runs or counts
    rows: Optional[RowsSpec] = None
    recompute: list[RecomputeSpec] = []
    null_baselines: list[NullSpec] = []
    recompute_exempt: dict[str, str] = {}  # metric -> written reason it cannot be recomputed from rows
    dev_rows: Optional[str] = None  # committed rows from a dev-seed run, checked for null discrimination at registration


class MetricValue(_Strict):
    value: float
    ci: Optional[tuple[float, float]] = None
    level: float = 0.95
    n: Optional[int] = None
    unit: str = ""


class SanityResult(_Strict):
    name: str
    passed: bool
    value: Optional[float] = None
    threshold: Optional[float] = None
    detail: str = ""


class Provenance(_Strict):
    git_commit: str
    git_dirty: bool
    git_branch: str = ""
    spec_hash: Optional[str] = None
    lock_hash: Optional[str] = None
    python: str = ""
    platform: str = ""
    host: str = ""
    packages: dict[str, str] = {}
    tools: dict[str, str] = {}
    started: str = ""
    finished: str = ""
    # Recorded by `mfos exp run` (not by the runner) for evidence-rules-v2 specs:
    code: dict[str, str] = {}  # code_under_test file -> sha256 in the checkout that ran
    runner_hashes: dict[str, str] = {}  # runner file -> sha256 in the checkout that ran


class ArtifactRef(_Strict):
    name: str
    sha256: str
    bytes: int


class ExperimentResult(_Strict):
    experiment_id: str
    run_id: str
    status: Literal["complete", "invalid", "error"]
    seed: Optional[int] = None
    config: dict[str, Any] = {}
    provenance: Provenance
    metrics: dict[str, MetricValue] = {}
    sanity: list[SanityResult] = []
    artifacts: list[ArtifactRef] = []
    notes: str = ""
    domain: dict[str, list[Any]] = {}  # values actually sampled (ExperimentRun.domain): the source of a claim's scope


# --------------------------------------------------------------------------- evaluation
class CriterionVerdict(_Strict):
    id: str
    metric: str
    comparator: str
    threshold: float
    value: Optional[float] = None
    bound_used: Optional[float] = None
    verdict: Literal["satisfied", "not_satisfied", "undetermined", "missing", "non_discriminating"]
    recomputed: Optional[bool] = None  # rules v2: the value was recomputed from the rows by the evaluator
    runner_value: Optional[float] = None
    null_value: Optional[float] = None  # the declared null predictor's value of the same metric
    null_bound: Optional[float] = None


class Evaluation(_Strict):
    id: str
    objective: str
    timestamp: str
    criteria_hash: Optional[str]
    evaluator_version: str
    results_used: dict[str, str]  # experiment id -> run id
    validity_problems: list[str]
    pass_checks: list[CriterionVerdict]
    fail_checks: list[CriterionVerdict]
    verdict: Literal["PASS", "FAIL", "INCONCLUSIVE", "INVALID"]
    explanation: str
    unused_runs: dict[str, list[str]] = {}  # experiment -> complete runs this evaluation did not use (rules v2)
    checks: dict[str, dict[str, str]] = {}  # experiment -> admissibility check -> "ok" | "n/a: ..." | reason


# --------------------------------------------------------------------------- inbox
class InboxItem(_Strict):
    id: str
    kind: Literal[
        "objective_approval", "plan_approval", "experiment_registration",
        "criteria_change", "budget_increase", "protected_change",
        "external_action", "thesis_change", "model_escalation", "decision", "question",
        "infrastructure", "claim_approval",
    ]
    subject: str
    summary: str
    refs: list[str] = []
    options: list[str] = []
    recommendation: str = ""
    status: Literal["open", "approved", "rejected", "answered"] = "open"
    response: str = ""
    created_at: str = ""
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None  # "human" (confirmed at a terminal) or "session" (e.g. an interactive AI session)


# --------------------------------------------------------------------------- claims
class Annotation(_Strict):
    at: str
    by: str
    note: str
    decision: Optional[str] = None  # decision record, e.g. D0006


class Claim(_Strict):
    id: str
    statement: str
    scope: str
    status: Literal["proposed", "supported", "refuted", "retracted"]
    objective: str
    evaluation: str
    reviews: list[str] = []
    caveats: list[str] = []
    created_at: str = ""
    # since the audit of 2026-10-19: claims start `proposed` with a scope generated from what was sampled, and become
    # `supported` only when the founder approves the wording at a terminal; later restrictions are appended, never
    # rewritten.
    domain: dict[str, list[Any]] = {}
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    scope_restrictions: list[str] = []
    annotations: list[Annotation] = []


# --------------------------------------------------------------------------- agent outputs
class TaskSpec(_Strict):
    """What the planner may propose. The orchestrator assigns ids and validates."""

    local_id: str = Field(description="Temporary id like 'n1' used for depends_on inside this plan")
    title: str
    type: Literal["implement", "experiment", "investigate", "design_experiment", "research", "docs"]
    agent: Literal["builder", "scientist", "scout", "none"]
    depends_on: list[str] = Field(default=[], description="Existing task ids or local_ids from this plan")
    description: str
    context_files: list[str] = []
    deliverables: list[str] = []
    touches: list[str] = []
    definition_of_done: list[DoDCheck] = []
    experiment: Optional[str] = None
    risk: Risk = "low"
    budget_usd: float = 3.0
    max_turns: int = 80
    rationale: str = ""


class CancelSpec(_Strict):
    id: str
    reason: str


class FounderRequest(_Strict):
    kind: Literal["decision", "question", "budget_increase", "criteria_change", "thesis_change", "model_escalation", "external_action"]
    subject: str
    summary: str
    options: list[str] = []
    recommendation: str = ""


class PlanOutput(_Strict):
    assessment: str = Field(description="Where the objective stands and why this plan")
    create_tasks: list[TaskSpec] = []
    cancel_tasks: list[CancelSpec] = []
    founder_requests: list[FounderRequest] = []
    evidence_complete: bool = Field(default=False, description="True when every required experiment has a task")


class CheckRun(_Strict):
    cmd: str
    exit_code: int


class BuildReport(_Strict):
    status: Literal["completed", "blocked", "partial"]
    summary: str
    files_changed: list[str] = []
    checks_run: list[CheckRun] = []
    concerns: list[str] = []


class Alternative(_Strict):
    explanation: str
    how_to_discriminate: str


class ScienceReport(_Strict):
    """Scientist output. For diagnosis tasks the failure fields are mandatory in spirit;
    for design/investigation tasks failure_class is 'none'."""

    summary: str
    failure_class: Literal["implementation", "model", "experimental", "planning", "business", "infrastructure",
                           "none"] = "none"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    root_cause: str = ""
    evidence: list[str] = []
    alternative_explanations: list[Alternative] = []
    discriminating_tests: list[str] = []
    recommended_actions: list[str] = []
    affects_acceptance_criteria: bool = False
    files_written: list[str] = []
    experiment_drafts: list[str] = Field(default=[], description="Paths of draft specs under experiments/drafts/")


class Finding(_Strict):
    severity: Literal["blocker", "major", "minor", "note"]
    title: str
    detail: str
    evidence: str = ""
    suggested_check: str = ""


class Review(_Strict):
    verdict: Literal["accept", "accept_with_caveats", "reject", "cannot_assess"]
    findings: list[Finding] = []
    independent_checks_performed: list[str] = []
    caveats: list[str] = []


class KeyFinding(_Strict):
    claim: str
    source: str
    confidence: Literal["high", "medium", "low"]


class ResearchReport(_Strict):
    summary: str
    notes_file: str
    key_findings: list[KeyFinding] = []
    open_questions: list[str] = []
    thesis_impact: Literal["none", "weakens", "strengthens", "unclear"] = "none"


class ScribeReport(_Strict):
    summary: str
    files_written: list[str] = []


ROLE_OUTPUT: dict[str, type[BaseModel]] = {
    "planner": PlanOutput,
    "builder": BuildReport,
    "scientist": ScienceReport,
    "critic": Review,
    "scout": ResearchReport,
    "scribe": ScribeReport,
}


# Spec fields added after the first registrations. Store.spec_hash leaves each out while it holds its default.
SPEC_FIELDS_HASHED_WHEN_SET = ("evidence_rules", "code_under_test", "code_must_match", "requires_passed", "rows",
                               "recompute", "null_baselines", "recompute_exempt", "dev_rows")
