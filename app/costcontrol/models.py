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
    scope_items: Mapped[list["ProjectScopeItem"]] = relationship(
        back_populates="project_ref", cascade="all, delete-orphan", order_by="ProjectScopeItem.id"
    )


class WorkType(Base):
    __tablename__ = "work_types"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    requires_modifies_ppe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ifrs_treatment: Mapped[str] = mapped_column(Text, nullable=False, default="")


class PlantArea(Base):
    __tablename__ = "plant_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(4), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("plant_areas.id"), nullable=True)
    is_ppe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    useful_life_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    asset_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    sars_tax_classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    existing_or_new: Mapped[str | None] = mapped_column(String(20), nullable=True)


class IndirectL2Account(Base):
    __tablename__ = "indirect_l2_accounts"

    code: Mapped[str] = mapped_column(String(7), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_l1: Mapped[str] = mapped_column(String(3), ForeignKey("control_accounts.code"), nullable=False)


class BudgetReserveSubAccount(Base):
    __tablename__ = "budget_reserve_subaccounts"

    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="")


class BudgetReserveBalance(Base):
    __tablename__ = "budget_reserve_balances"
    __table_args__ = (UniqueConstraint("project_number", "reserve_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_number: Mapped[str] = mapped_column(String(20), ForeignKey("projects.project_number"), nullable=False, index=True)
    reserve_code: Mapped[str] = mapped_column(String(6), ForeignKey("budget_reserve_subaccounts.code"), nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)

    reserve_ref: Mapped["BudgetReserveSubAccount"] = relationship()


class ProjectScopeItem(Base):
    __tablename__ = "project_scope_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_number: Mapped[str] = mapped_column(String(20), ForeignKey("projects.project_number"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    work_type_code: Mapped[str | None] = mapped_column(String(30), ForeignKey("work_types.code"), nullable=True)
    modifies_ppe_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    project_ref: Mapped["Project"] = relationship(back_populates="scope_items")
    work_type_ref: Mapped["WorkType | None"] = relationship()
    cost_components: Mapped[list["CostComponent"]] = relationship(
        back_populates="scope_item_ref", cascade="all, delete-orphan", order_by="CostComponent.cbs_l2_code"
    )


class CostComponent(Base):
    __tablename__ = "cost_components"
    __table_args__ = (UniqueConstraint("project_number", "cbs_l2_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_number: Mapped[str] = mapped_column(String(20), ForeignKey("projects.project_number"), nullable=False, index=True)
    scope_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("project_scope_items.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    commodity_code: Mapped[str] = mapped_column(String(3), ForeignKey("control_accounts.code"), nullable=False)
    cbs_l2_code: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="Provisional")
    type_discriminator: Mapped[str] = mapped_column(String(20), nullable=False, default="Asset")

    scope_item_ref: Mapped["ProjectScopeItem"] = relationship(back_populates="cost_components")
    commodity_ref: Mapped["ControlAccount"] = relationship()
    plant_area_links: Mapped[list["CostComponentPlantArea"]] = relationship(
        back_populates="cost_component_ref", cascade="all, delete-orphan"
    )
    cost_item_codes: Mapped[list["CostItemCode"]] = relationship(
        back_populates="cost_component_ref", cascade="all, delete-orphan", order_by="CostItemCode.code"
    )


class CostComponentPlantArea(Base):
    __tablename__ = "cost_component_plant_areas"
    __table_args__ = (UniqueConstraint("cost_component_id", "plant_area_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cost_component_id: Mapped[int] = mapped_column(Integer, ForeignKey("cost_components.id", ondelete="CASCADE"), nullable=False)
    plant_area_id: Mapped[int] = mapped_column(Integer, ForeignKey("plant_areas.id"), nullable=False)

    cost_component_ref: Mapped["CostComponent"] = relationship(back_populates="plant_area_links")
    plant_area_ref: Mapped["PlantArea"] = relationship()


class CostItemCode(Base):
    __tablename__ = "cost_item_codes"
    __table_args__ = (
        UniqueConstraint("project_number", "code"),
        UniqueConstraint("cost_component_id", "sequence"),
        UniqueConstraint("indirect_l2_code", "sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_number: Mapped[str] = mapped_column(String(20), ForeignKey("projects.project_number"), nullable=False, index=True)
    cost_component_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cost_components.id", ondelete="CASCADE"), nullable=True)
    indirect_l2_code: Mapped[str | None] = mapped_column(String(7), ForeignKey("indirect_l2_accounts.code"), nullable=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="custom")

    cost_component_ref: Mapped["CostComponent | None"] = relationship(back_populates="cost_item_codes")
    indirect_l2_ref: Mapped["IndirectL2Account | None"] = relationship()


class PackageCostItem(Base):
    __tablename__ = "package_cost_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True)
    cost_item_code_id: Mapped[int] = mapped_column(Integer, ForeignKey("cost_item_codes.id"), nullable=False, index=True)
    cbs_l2_code: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)
    provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Draft")
    superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    superseded_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("package_cost_items.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    package_ref: Mapped["Package"] = relationship(back_populates="cost_items", foreign_keys=[package_id])
    cost_item_code_ref: Mapped["CostItemCode"] = relationship()


class CostControlAuditLog(Base):
    __tablename__ = "cost_control_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


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
    package_source: Mapped[str] = mapped_column(String(20), nullable=False, default="Internal")
    pricing_basis: Mapped[str] = mapped_column(String(10), nullable=False, default="LS")
    planned_value: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=False, default=0)
    # Procurement-side post-award fields. Only meaningful when is_external=True.
    awarded_vendor_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    awarded_amount: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    awarded_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # DEPRECATED 2026-05-05 — superseded by package_stage, which carries the
    # canonical four-stage lifecycle (Definition / Procurement / Execution /
    # Close-out) per the Schedule Estimation Standards. The column stays in
    # the schema for backward compatibility (SQLite ALTER TABLE DROP is
    # awkward) but is no longer read or written by the app.
    procurement_stage: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Pre-Tender"
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project_ref: Mapped["Project"] = relationship(back_populates="packages")
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
    cost_items: Mapped[list["PackageCostItem"]] = relationship(
        back_populates="package_ref", cascade="all, delete-orphan", order_by="PackageCostItem.id"
    )
    cost_sheets: Mapped[list["PackageCostSheet"]] = relationship(
        back_populates="package_ref", cascade="all, delete-orphan", order_by="PackageCostSheet.display_order"
    )
    documents: Mapped[list["PackageDocument"]] = relationship(
        back_populates="package_ref", cascade="all, delete-orphan"
    )


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


class PackageCostSheet(Base):
    __tablename__ = "package_cost_sheets"
    __table_args__ = (UniqueConstraint("package_id", "sheet_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_number: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_type: Mapped[str] = mapped_column(String(20), nullable=False, default="Original")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Draft")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_sheet_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("package_cost_sheets.id"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    package_ref: Mapped["Package"] = relationship(back_populates="cost_sheets")
    cost_nodes: Mapped[list["PackageCostNode"]] = relationship(
        back_populates="cost_sheet_ref",
        cascade="all, delete-orphan",
        foreign_keys="PackageCostNode.cost_sheet_id",
    )


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
    cost_sheet_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("package_cost_sheets.id", ondelete="CASCADE"), nullable=True, index=True
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
    cost_sheet_ref: Mapped["PackageCostSheet | None"] = relationship(
        back_populates="cost_nodes", foreign_keys=[cost_sheet_id]
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


class PackageDocument(Base):
    __tablename__ = "package_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Planned")
    revision: Mapped[str | None] = mapped_column(String(10), nullable=True)
    planned_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    package_ref: Mapped["Package"] = relationship(back_populates="documents")


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
    # Slice B — every RTO belongs to exactly one package. Required at the
    # model layer; SQLite column itself stays nullable for back-compat with
    # existing schemas (no rows had NULL in practice).
    package_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
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


class Tender(Base):
    """A tender event raised against an external package. Holds the request,
    bidders, bid documents, and (in later slices) evaluation criteria/scores
    + award outcome. v1 has one Tender per package, but the .TND.NNN suffix
    leaves room for re-tenders.
    """

    __tablename__ = "tender"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Draft")
    # Draft / Issued / Closed / Adjudicating / Awarded / Cancelled
    adjudication_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    package_ref: Mapped["Package"] = relationship()
    bidders: Mapped[list["Bidder"]] = relationship(
        back_populates="tender_ref", cascade="all, delete-orphan", order_by="Bidder.display_order"
    )


class Bidder(Base):
    """A bidder on a Tender. Tracks vendor name, bid amount, status, and
    holds attached document references (links to network paths/URLs)."""

    __tablename__ = "bidder"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bid_amount: Mapped[float | None] = mapped_column(Numeric(18, 2, asdecimal=False), nullable=True)
    bid_received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending")
    # Pending / Submitted / Withdrawn / Disqualified / Shortlisted / Awarded
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tender_ref: Mapped["Tender"] = relationship(back_populates="bidders")
    documents: Mapped[list["BidDocument"]] = relationship(
        back_populates="bidder_ref", cascade="all, delete-orphan", order_by="BidDocument.id"
    )


class EvaluationCriterion(Base):
    """A weighted criterion against which bidders are scored. Defined once
    per tender; bidders are scored on each criterion via BidEvaluation rows.
    Weights are intended to sum to 100 across criteria for a tender — soft
    constraint enforced as a UI warning, not a DB invariant."""

    __tablename__ = "evaluation_criterion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weight: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BidEvaluation(Base):
    """One score per (bidder, criterion). Score is 0-100; the weighted total
    per bidder is sum(score * weight) / sum(weights), surfaced on the
    Adjudication view."""

    __tablename__ = "bid_evaluation"
    __table_args__ = (UniqueConstraint("bidder_id", "criterion_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bidder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bidder.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluation_criterion.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False, default=0)
    evaluator: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class BidDocument(Base):
    """Reference to a bid-related document. v1 stores a name + link/URL/path
    only — no binary uploads. The user pastes a network-drive link or
    filename so the team can find the document outside the app."""

    __tablename__ = "bid_document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bidder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bidder.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    document_ref: Mapped[str] = mapped_column(Text, nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    bidder_ref: Mapped["Bidder"] = relationship(back_populates="documents")


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
    # Slice E — first PO linked to an RTO is the "original" contract; later
    # links are variations. Auto-flagged at link-time based on chronology
    # (no other links yet → original); manually overridable.
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
