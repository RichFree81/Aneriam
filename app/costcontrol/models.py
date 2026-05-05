from datetime import date, datetime
from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class ControlAccount(Base):
    __tablename__ = "control_accounts"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    excluded_from_capex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    direct_indirect: Mapped[str | None] = mapped_column(String(10), nullable=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_budget: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    approved_capex: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    planned_fy2027: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="project_ref")
    packages: Mapped[list["Package"]] = relationship(back_populates="project_ref", order_by="Package.display_order")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    source_files: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="batch")


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_number: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    leaf_name: Mapped[str] = mapped_column(Text, nullable=False)
    level1: Mapped[str] = mapped_column(Text, nullable=False)
    level2: Mapped[str | None] = mapped_column(Text, nullable=True)
    level3: Mapped[str | None] = mapped_column(Text, nullable=True)
    # C-3 — added 2026-05-04 per app revision plan v1
    project_status: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    project_number: Mapped[str] = mapped_column(
        String(20), ForeignKey("projects.project_number"), nullable=False
    )
    project_task_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    activity_code_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(Text, nullable=False, default="")
    document_number: Mapped[str] = mapped_column(Text, nullable=False, default="")
    vendor_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    po_number: Mapped[str] = mapped_column(Text, nullable=False, default="")
    po_description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    netsuite_actual: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)
    netsuite_committed: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)
    netsuite_cost: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)

    # C-1 — PMO 18-column additions, 2026-05-04
    account_full_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fiscal_year: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fiscal_quarter: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transaction_date_created: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_date_closed: Mapped[date | None] = mapped_column(Date, nullable=True)

    derived_cc_code: Mapped[str] = mapped_column(String(3), nullable=False, default="")
    derived_cc_name: Mapped[str] = mapped_column(Text, nullable=False, default="Unallocated")

    actual_cost: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)
    committed_cost: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)

    import_batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("import_batches.id"), nullable=False
    )
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)

    project_ref: Mapped["Project"] = relationship(back_populates="transactions")
    batch: Mapped["ImportBatch"] = relationship(back_populates="transactions")


class PurchaseOrderLine(Base):
    __tablename__ = "po_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    project_number: Mapped[str] = mapped_column(String(20), nullable=False)
    memo_main: Mapped[str] = mapped_column(Text, nullable=False, default="")
    memo: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # `name` historically held the Project Task path (colon-separated). Under the
    # new PO Detailed layout the equivalent column is `Project Task Name`.
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)
    actual_amount: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    # C-2 — PO Detailed new columns, 2026-05-04
    internal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)
    actual: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)
    vendor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class JournalLine(Base):
    """C-4 — Journal Entries Detailed (NetSuite saved search id=790).

    One row per journal posting line. Stored separately from `transactions`
    (which is sourced from PMO Projects Report) so the two pipes can be
    reconciled per source without one polluting the other.
    """

    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_number: Mapped[str] = mapped_column(Text, nullable=False, default="")
    project_number: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    account_full_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    type: Mapped[str] = mapped_column(Text, nullable=False, default="")
    memo_main: Mapped[str] = mapped_column(Text, nullable=False, default="")
    memo: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    period: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approval_status: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="")
    import_batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("import_batches.id"), nullable=False
    )


class GLLine(Base):
    """C-4 — Project GL Detailed (NetSuite saved search id=791).

    All project-tagged GL postings. Includes a `posting` flag so we can
    distinguish posting from non-posting transactions if needed.
    """

    __tablename__ = "gl_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_number: Mapped[str] = mapped_column(Text, nullable=False, default="")
    project_number: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    account_full_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    type: Mapped[str] = mapped_column(Text, nullable=False, default="")
    memo_main: Mapped[str] = mapped_column(Text, nullable=False, default="")
    memo: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    period: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="")
    posting: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    import_batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("import_batches.id"), nullable=False
    )


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    project_number: Mapped[str] = mapped_column(String(20), ForeignKey("projects.project_number"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    package_type: Mapped[str] = mapped_column(String(60), nullable=False)
    package_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimation_standard: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # True once contract amounts are locked in — freezes the pre-award column
    is_contracted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Internal packages (in-house design / EPCM time) skip the procurement
    # workflow entirely — only Cost Buildup applies. External packages run
    # tender → adjudication → award → RTO → original PO → variations.
    # Default is set per package_type at seed time (see seed.default_is_external).
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Procurement-side post-award fields. Only meaningful when is_external=True.
    awarded_vendor_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    awarded_amount: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    awarded_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    procurement_stage: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Pre-Tender"
    )  # Pre-Tender / Tender Issued / Bids In / Adjudicating / Awarded / Active / Closed
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project_ref: Mapped["Project"] = relationship(back_populates="packages")
    workstreams: Mapped[list["Workstream"]] = relationship(
        back_populates="package_ref", cascade="all, delete-orphan", order_by="Workstream.display_order"
    )
    schedule_stages: Mapped[list["PackageScheduleStage"]] = relationship(
        back_populates="package_ref", cascade="all, delete-orphan", order_by="PackageScheduleStage.stage_order"
    )
    schedule_inputs: Mapped[list["PackageScheduleInput"]] = relationship(
        back_populates="package_ref", cascade="all, delete-orphan"
    )
    cost_nodes: Mapped[list["PackageCostNode"]] = relationship(
        back_populates="package_ref",
        cascade="all, delete-orphan",
        foreign_keys="PackageCostNode.package_id",
    )
    deliverables: Mapped[list["PackageDeliverable"]] = relationship(
        back_populates="package_ref", cascade="all, delete-orphan"
    )


class Workstream(Base):
    __tablename__ = "workstreams"
    __table_args__ = (UniqueConstraint("package_id", "ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    ref: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    package_ref: Mapped["Package"] = relationship(back_populates="workstreams")
    deliverables: Mapped[list["PackageDeliverable"]] = relationship(back_populates="workstream_ref")


class PackageScheduleStage(Base):
    __tablename__ = "package_schedule_stages"
    __table_args__ = (UniqueConstraint("package_id", "stage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    base_weeks: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False), nullable=True)
    review_approval_weeks: Mapped[float | None] = mapped_column(Numeric(4, 1, asdecimal=False), nullable=True)
    expert_adjustment_weeks: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)
    expert_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_weeks: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    package_ref: Mapped["Package"] = relationship(back_populates="schedule_stages")


class PackageScheduleInput(Base):
    __tablename__ = "package_schedule_inputs"
    __table_args__ = (UniqueConstraint("package_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    package_ref: Mapped["Package"] = relationship(back_populates="schedule_inputs")


class PackageCostNode(Base):
    """One row per node in a package's cost breakdown structure.

    Nodes form a self-referential tree (adjacency list, up to 4 levels deep).
    Any node can be a cost item (is_item=True) — group-only nodes roll up
    their children's amounts for display.

    Columns:
        baseline_amount   — initial estimate, locked once baseline is set
        pre_award_amount  — working estimate; frozen when package.is_contracted=True
        contract_amount   — contractor-awarded amount, locked once entered
    """

    __tablename__ = "package_cost_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("package_cost_nodes.id", ondelete="CASCADE"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # True when this node directly holds cost amounts (vs. being a group header)
    is_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Only relevant when is_item=True
    cc_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("control_accounts.code"), nullable=True
    )
    workstream_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workstreams.id", ondelete="SET NULL"), nullable=True
    )

    # Baseline
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="Sum")
    qty: Mapped[float | None] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=True)
    rate: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    baseline_amount: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)

    # Pre-award estimate
    pre_award_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="Sum")
    pre_award_qty: Mapped[float | None] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=True)
    pre_award_rate: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    pre_award_amount: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)

    # Contract value
    contract_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="Sum")
    contract_qty: Mapped[float | None] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=True)
    contract_rate: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    contract_amount: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)

    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    package_ref: Mapped["Package"] = relationship(
        back_populates="cost_nodes", foreign_keys=[package_id]
    )
    parent: Mapped["PackageCostNode | None"] = relationship(
        back_populates="children", remote_side="PackageCostNode.id", foreign_keys=[parent_id]
    )
    children: Mapped[list["PackageCostNode"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
        order_by="PackageCostNode.display_order",
    )
    cc_ref: Mapped["ControlAccount | None"] = relationship(foreign_keys=[cc_code])
    workstream_ref: Mapped["Workstream | None"] = relationship(foreign_keys=[workstream_id])


class CostNodeAuditLog(Base):
    """One row per save on a PackageCostNode — records a full snapshot of all
    three cost columns so the view modal can show the complete change history."""

    __tablename__ = "cost_node_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cost_node_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("package_cost_nodes.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # 'Created' | 'Updated'
    # No default — `_write_audit_log` always supplies a local-time value via
    # `datetime.now()`. A `func.now()` default would be UTC and would conflict
    # with the explicit local writes if any future code path forgot to pass it.
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON


class PackageDeliverable(Base):
    __tablename__ = "package_deliverables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    workstream_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("workstreams.id", ondelete="SET NULL"), nullable=True)
    ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Planned")
    revision: Mapped[str | None] = mapped_column(String(10), nullable=True)
    planned_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    package_ref: Mapped["Package"] = relationship(back_populates="deliverables")
    workstream_ref: Mapped["Workstream | None"] = relationship(back_populates="deliverables")


class RTO(Base):
    """Request To Order — a header-only record raised before a NetSuite PO is
    issued. Carries vendor, total amount, and a status that walks through
    Draft → Submitted → Approved → Issued for PO → Cancelled. Linked to one
    NetSuite PO via `po_rto_links` once Procurement raises it.
    """

    __tablename__ = "rto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rto_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    project_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    package_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vendor_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Draft")
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    originator: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Local-time stamps, same convention as cost_node_audit_log.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PORtoLink(Base):
    """Link between a NetSuite PO and an RTO. One PO can be linked to at most
    one RTO (UNIQUE on po_number). Source distinguishes manual user link from
    future auto-matchers (e.g. memo-regex)."""

    __tablename__ = "po_rto_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    rto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rto.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    linked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    linked_by: Mapped[str] = mapped_column(Text, nullable=False, default="")
