"""Module defining the configuration settings for the histopathology simulation model.

The configuration settings are defined using Pydantic, and are fully convertable to JSON.
To actually run a simulation, the configuration settings (as a :py:class:`hpath.config.Config`
object) are converted to a :py:class:`hpath.model.Model` object, which contain the actual Python
objects used for :py:class:`~salabim.Resource` tracking, etc.
"""
import typing as ty

import networkx as nx
import openpyxl as xl
import pandas as pd
import pydantic as pyd

from . import excel as xlh

Probability = pyd.confloat(ge=0, le=1)


class ArrivalSchedule(pyd.BaseModel):
    """An arrival schedule for specimens."""
    rates: ty.Sequence[pyd.NonNegativeFloat]

    @pyd.field_validator('rates', mode='after')
    @classmethod
    def _check_length_168(
        cls, seq: ty.Sequence[pyd.NonNegativeFloat]
    ) -> ty.Sequence[pyd.NonNegativeFloat]:
        """Enforce sequence length on  ``day_flags`` argument."""
        assert len(seq) == 168, 'Length of sequence must be 168.'
        return seq

    @staticmethod
    def from_pd(df: pd.DataFrame) -> 'ArrivalSchedule':
        """Construct an arrival schedule from a dataframe with the 24 hours the day as rows
        and the seven days of the week as columns (starting on Monday).  Each value is the
        arrival rate for one hour of the week.

        Args:
            df (pandas.DataFrame):
                The dataframe containing the arrival schedule information.
        """
        return __class__(rates=df.to_numpy().flatten('F').tolist())


class ArrivalSchedules(pyd.BaseModel):
    """Dataclass for tracking the specimen arrival schedules of a model."""

    cancer: ArrivalSchedule
    """Arrival schedule for cancer pathway specimens."""

    noncancer: ArrivalSchedule
    """Arrival schedule for non-cancer pathway specimens."""


class ResourceSchedule(pyd.BaseModel):
    """A resource allocation schedule."""

    day_flags: ty.Sequence[bool]
    """True/1 if resource is scheduled for the day (MON to SUN), False/0 otherwise."""

    allocation: ty.Sequence[pyd.NonNegativeInt]
    """Number of resource units allocated for the day (in 30-min intervals),
    if the corresponding day flag is set to 1. The list length is expected to be 48."""

    @pyd.field_validator('day_flags', mode='after')
    @classmethod
    def _check_length_7(cls, seq: ty.Sequence[bool]) -> ty.Sequence[bool]:
        """Enforce sequence length on  ``day_flags`` argument."""
        assert len(seq) == 7, 'Length of sequence must be 7.'
        return seq

    @pyd.field_validator('allocation', mode='after')
    @classmethod
    def _check_length_48(cls, seq: ty.Sequence[bool]) -> ty.Sequence[bool]:
        """Enforce sequence length on  ``allocation`` argument."""
        assert len(seq) == 48, 'Length of sequence must be 48.'
        return seq

    @staticmethod
    def from_pd(df: pd.DataFrame, row_name: str) -> 'ResourceSchedule':
        """Construct a resource schedule from a DataFrame row.

        Args:
            df (pandas.DataFrame):
                The dataframe containing the resource allocation information.
            row_name (str):
                The name of the resource, matching a row index in the inputted dataframe.
        """
        return __class__(
            day_flags=df.loc[row_name, 'MON':'SUN'].tolist(),
            allocation=df.loc[row_name, '00:00':'23:30'].tolist()
        )


class ResourceInfo(pyd.BaseModel):
    """Contains information about a resource."""
    name: str
    """The name of the resource, e.g. "Scanning machine"."""

    type: ty.Literal['staff', 'machine']
    """Whether the resource is a staff or machine resource."""

    schedule: ResourceSchedule
    """A schedule defining the number of allocated resource units over the course of a week."""


class ResourcesInfo(pyd.BaseModel):
    """Dataclass for tracking the staff resources of a model.

    The fields in this dataclass **MUST** match the rows of the configuration
    Excel template ("Resources" tab), with all letters to lowercase, spaces to
    underscores, and other characters removed."""

    booking_in_staff: ResourceInfo =\
        pyd.Field(title='Booking-in staff', json_schema_extra={'resource_type': 'staff'})
    bms: ResourceInfo =\
        pyd.Field(title='BMS', json_schema_extra={'resource_type': 'staff'})
    cut_up_assistant: ResourceInfo =\
        pyd.Field(title='Cut-up assistant', json_schema_extra={'resource_type': 'staff'})
    processing_room_staff: ResourceInfo =\
        pyd.Field(title='Processing room staff', json_schema_extra={'resource_type': 'staff'})
    microtomy_staff: ResourceInfo =\
        pyd.Field(title='Microtomy staff', json_schema_extra={'resource_type': 'staff'})
    staining_staff: ResourceInfo =\
        pyd.Field(title='Staining staff', json_schema_extra={'resource_type': 'staff'})
    scanning_staff: ResourceInfo =\
        pyd.Field(title='Scanning staff', json_schema_extra={'resource_type': 'staff'})
    qc_staff: ResourceInfo =\
        pyd.Field(title='QC staff', json_schema_extra={'resource_type': 'staff'})
    histopathologist: ResourceInfo =\
        pyd.Field(title='Histopathologist', json_schema_extra={'resource_type': 'staff'})
    bone_station: ResourceInfo =\
        pyd.Field(title='Bone station', json_schema_extra={'resource_type': 'machine'})
    processing_machine: ResourceInfo =\
        pyd.Field(title='Processing machine', json_schema_extra={'resource_type': 'machine'})
    staining_machine: ResourceInfo =\
        pyd.Field(title='Staining machine', json_schema_extra={'resource_type': 'machine'})
    coverslip_machine: ResourceInfo =\
        pyd.Field(title='Coverslip machine', json_schema_extra={'resource_type': 'machine'})
    scanning_machine_regular: ResourceInfo = pyd.Field(
        title='Scanning machine (regular)', json_schema_extra={'resource_type': 'machine'})
    scanning_machine_megas: ResourceInfo = pyd.Field(
        title='Scanning machine (megas)', json_schema_extra={'resource_type': 'machine'})

    @staticmethod
    def from_pd(df: pd.DataFrame) -> 'ResourcesInfo':
        """Construct a ``ResourcesInfo`` object from a pandas dataframe.

        Args:
            df (pandas.DataFrame):
                The dataframe containing the resource allocation information.
        """
        resources = {
            key: ResourceInfo(
                name=field.title,
                type=field.json_schema_extra['resource_type'],
                schedule=ResourceSchedule.from_pd(df, row_name=key)
            )
            for key, field in __class__.model_fields.items()
        }
        return __class__(**resources)


class DistributionInfo(pyd.BaseModel):
    """Information describing a three-point random distributions for task durations."""

    type: ty.Literal['Constant', 'Triangular', 'PERT']  # Supported distribution types
    """The type of the distribution, one of 'Constant', 'Triangular', or 'PERT'."""

    low: pyd.NonNegativeFloat
    """The minimum value of the distribution."""

    mode: pyd.NonNegativeFloat
    """The most likely value of the distribution."""

    high: pyd.NonNegativeFloat
    """The maximum of the distribution."""

    time_unit: ty.Literal['s', 'm', 'h']
    """The time unit of the distribution, i.e. seconds, minutes, or hours.  Represented by the
    first letter; the validator will accept any string starting with 's', 'm', or 'h'."""

    @pyd.field_validator('time_unit', mode='before')
    @classmethod
    def _first_letter(cls, time_unit_str: str) -> str:
        """Take only the first letter from a time-unit string.

        For simplicity, only the first character of time-unit strings are checked, i.e.
        "hours", "hour", and "hxar" are identical.
        """
        assert time_unit_str[0] in ['s', 'm', 'h']
        return time_unit_str[0]

    @pyd.model_validator(mode='after')
    def _enforce_ordering(self) -> 'DistributionInfo':
        """Ensure that the the ``low``, ``mode`` and ``high`` parameters of the distribution
        are in non-decreasing order."""
        # Constant case
        if self.type == 'Constant':
            return __class__.model_construct(
                type='Constant', low=self.mode, mode=self.mode, high=self.mode,
                time_unit=self.time_unit
            )
        # Other cases
        assert self.mode >= self.low, 'Failed requirement: mode >= low'
        assert self.high >= self.mode, 'Failed requirement: high >= mode'
        return self


class TaskDurationsInfo(pyd.BaseModel):
    """Information for tracking task durations in a model.

    The field titles in this class **MUST** match the rows of the Excel input file
    ("Task Durations" tab)."""

    receive_and_sort: DistributionInfo = pyd.Field(title='Receive and sort')
    """Time for reception to receive a new specimen and assign a priority value."""

    pre_booking_in_investigation: DistributionInfo = pyd.Field(title='Pre-booking-in investigation')
    """Time to conduct a pre-booking-in investigation, if required."""

    booking_in_internal: DistributionInfo = pyd.Field(title='Booking-in (internal)')
    """Time to book in the specimen if the specimen was received internally, i.e. it already
    exists on the EPIC sytem."""

    booking_in_external: DistributionInfo = pyd.Field(title='Booking-in (external)')
    """Time to book in the specimen if the specimen was received externally, i.e. a new entry
    must be created on EPIC."""

    booking_in_investigation_internal_easy: DistributionInfo =\
        pyd.Field(title='Booking-in investigation (internal, easy)')
    """Time to conduct a booking-in investigation for an internal specimen, if the investigation
    is classified as "easy"."""

    booking_in_investigation_internal_hard: DistributionInfo =\
        pyd.Field(title='Booking-in investigation (internal, hard)')
    """Time to conduct a booking-in investigation for an internal specimen, if the investigation
    is classified as "hard"."""

    booking_in_investigation_external: DistributionInfo =\
        pyd.Field(title='Booking-in investigation (external)')
    """Time to conduct a booking-in investigation for an external specimen."""

    cut_up_bms: DistributionInfo = pyd.Field(title='Cut-up (BMS)')
    """Time to conduct a BMS cut-up."""

    cut_up_pool: DistributionInfo = pyd.Field(title='Cut-up (pool)')
    """Time to conduct a pool cut-up."""

    cut_up_large_specimens: DistributionInfo = pyd.Field(title='Cut-up (large specimens)')
    """Time to conduct a large specimens cut-up."""

    load_bone_station: DistributionInfo = pyd.Field(title='Load bone station')
    """Time to load a batch of blocks into a bone station."""

    decalc: DistributionInfo = pyd.Field(title='Decalc')
    """Time to decalcify a bony specimen."""

    unload_bone_station: DistributionInfo = pyd.Field(title='Unload bone station')
    """Time to unload a batch of blocks into a bone station."""

    load_into_decalc_oven: DistributionInfo = pyd.Field(title='Load into decalc oven')
    """Time to load a single block into a bone station."""

    unload_from_decalc_oven: DistributionInfo = pyd.Field(title='Unload from decalc oven')
    """Time to unload a single block into a bone station."""

    load_processing_machine: DistributionInfo = pyd.Field(title='Load processing machine')
    """Time to load a batch of blocks into a processing machine."""

    unload_processing_machine: DistributionInfo = pyd.Field(title='Unload processing machine')
    """Time to unload a batch of blocks from a processing machine."""

    processing_urgent: DistributionInfo = pyd.Field(title='Processing machine (urgent)')
    """Programme length for the processing of urgent blocks."""

    processing_small_surgicals: DistributionInfo =\
        pyd.Field(title='Processing machine (small surgicals)')
    """Programme length for the processing of small surgical blocks."""

    processing_large_surgicals: DistributionInfo =\
        pyd.Field(title='Processing machine (large surgicals)')
    """Programme length for the processing of large surgical blocks."""

    processing_megas: DistributionInfo = pyd.Field(title='Processing machine (megas)')
    """Programme length for the processing of mega blocks."""

    embedding: DistributionInfo = pyd.Field(title='Embedding')
    """Time to embed a block in paraffin wax (staffed)."""

    embedding_cooldown: DistributionInfo = pyd.Field(title='Embedding (cooldown)')
    """Time for a wax block to cool (unstaffed)."""

    block_trimming: DistributionInfo = pyd.Field(title='Block trimming')
    """Time to trim excess wax from the edges of a block."""

    microtomy_serials: DistributionInfo = pyd.Field(title='Microtomy (serials)')
    """Time to produce serial slides from a block."""

    microtomy_levels: DistributionInfo = pyd.Field(title='Microtomy (levels)')
    """Time to produce level slides from a block."""

    microtomy_larges: DistributionInfo = pyd.Field(title='Microtomy (larges)')
    """"Time to produce large-section slides from a block. These are regular-sized slides,
    but with larger tissue sections."""

    microtomy_megas: DistributionInfo = pyd.Field(title='Microtomy (megas)')
    """Time to produce mega slides from a mega block."""

    load_staining_machine_regular: DistributionInfo =\
        pyd.Field(title='Load staining machine (regular)')
    """Time to load a batch of regular-sized slides into a staining machine."""

    load_staining_machine_megas: DistributionInfo =\
        pyd.Field(title='Load staining machine (megas)')
    """Time to load a batch of mega slides into a staining machine."""

    staining_regular: DistributionInfo = pyd.Field(title='Staining (regular)')
    """Time to stain a batch of regular slides."""

    staining_megas: DistributionInfo = pyd.Field(title='Staining (megas)')
    """Time to stain a batch of mega slides."""

    unload_staining_machine_regular: DistributionInfo =\
        pyd.Field(title='Unload staining machine (regular)')
    """Time to unload a batch of regular slides from a staining machine."""

    unload_staining_machine_megas: DistributionInfo =\
        pyd.Field(title='Unload staining machine (megas)')
    """Time to unload a batch of mega slides from a staining machine."""

    load_coverslip_machine_regular: DistributionInfo =\
        pyd.Field(title='Load coverslip machine (regular)')
    """Time to load a batch of regular slides into a coverslip machine."""

    coverslip_regular: DistributionInfo = pyd.Field(title='Coverslipping (regular)')
    """Time to affix coverslips to a batch of regular slides."""

    coverslip_megas: DistributionInfo = pyd.Field(title='Coverslipping (megas)')
    """Time to affix a coverslip to a mega slide (manual task)."""

    unload_coverslip_machine_regular: DistributionInfo =\
        pyd.Field(title='Unload coverslip machine (regular)')
    """Time to unload a batch of regular slides into a coverslip machine."""

    labelling: DistributionInfo = pyd.Field(title='Labelling')
    """Time to label a slide."""

    load_scanning_machine_regular: DistributionInfo =\
        pyd.Field(title='Load scanning machine (regular)')
    """Time to load a batch of regular slides into a scanning machine."""

    load_scanning_machine_megas: DistributionInfo =\
        pyd.Field(title='Load scanning machine (megas)')
    """Time to load a batch of mega slides into a scanning machine. There are dedicated scanning
    machines for mega slides."""

    scanning_regular: DistributionInfo = pyd.Field(title='Scanning (regular)')
    """Time to scan a batch of regular slides."""

    scanning_megas: DistributionInfo = pyd.Field(title='Scanning (megas)')
    """Time to scan a batch of mega slides."""

    unload_scanning_machine_regular: DistributionInfo =\
        pyd.Field(title='Unload scanning machine (regular)')
    """Time to unload a batch of regular slides from a scanning machine."""

    unload_scanning_machine_megas: DistributionInfo =\
        pyd.Field(title='Unload scanning machine (megas)')
    """Time to unload a batch of mega slides from a scanning machine."""

    block_and_quality_check: DistributionInfo = pyd.Field(title='Block and quality check')
    """Time to perform the block and quality checks for a specimen."""

    assign_histopathologist: DistributionInfo = pyd.Field(title='Assign histopathologist')
    """Time to assign a histopathologist to a specimen."""

    write_report: DistributionInfo = pyd.Field(title='Write histopathological report')
    """Time to write the histopathological report for a specimen."""


class BatchSizes(pyd.BaseModel):
    """Information for tracking batch sizes in a model.  This is the number of
    specimens, blocks, or slides in a machine or delivery batch.  Batches in the model
    are homogeneous, i.e. all items in a batch are of the same type.

    The field titles in this class MUST match the rows of the Excel input file
    ("Batch Sizes" tab)."""

    deliver_reception_to_cut_up: pyd.PositiveInt =\
        pyd.Field(title='Delivery (reception to cut-up)')
    """Delivery batch size, reception to cut-up (specimens)."""

    deliver_cut_up_to_processing: pyd.PositiveInt =\
        pyd.Field(title='Delivery (cut-up to processing)')
    """Delivery batch size, cut-up to processing (specimens)."""

    deliver_processing_to_microtomy: pyd.PositiveInt =\
        pyd.Field(title='Delivery (processing to microtomy)')
    """Delivery batch size, processing to microtomy (specimens)."""

    deliver_microtomy_to_staining: pyd.PositiveInt =\
        pyd.Field(title='Delivery (microtomy to staining)')
    """Delivery batch size, microtomy to staining (specimens)."""

    deliver_staining_to_labelling: pyd.PositiveInt =\
        pyd.Field(title='Delivery (staining to labelling)')
    """Delivery batch size, staining to labelling (specimens)."""

    deliver_labelling_to_scanning: pyd.PositiveInt =\
        pyd.Field(title='Delivery (labelling to scanning)')
    """Delivery batch size, labelling to scanning (specimens)."""

    deliver_scanning_to_qc: pyd.PositiveInt = pyd.Field(title='Delivery (scanning to QC)')
    """Delivery batch size, scanning to QC (specimens)."""

    bone_station: pyd.PositiveInt = pyd.Field(title='Bone station (blocks)')
    """Bone station (machine) batch size (blocks)."""

    processing_regular: pyd.PositiveInt =\
        pyd.Field(title='Processing machine (regular blocks)')
    """Processing machine batch size, regular blocks."""

    processing_megas: pyd.PositiveInt = pyd.Field(title='Processing machine (mega blocks)')
    """Processing machine batch size, mega blocks."""

    staining_regular: pyd.PositiveInt = pyd.Field(title='Staining (regular slides)')
    """Staining machine batch size, regular slides."""

    staining_megas: pyd.PositiveInt = pyd.Field(title='Staining (mega slides)')
    """Staining machine batch size, mega slides."""

    digital_scanning_regular: pyd.PositiveInt = pyd.Field(title='Scanning (regular slides)')
    """Scanning machine batch size, regular slides."""

    digital_scanning_megas: pyd.PositiveInt = pyd.Field(title='Scanning (mega slides)')
    """Scanning machine batch size, mega slides."""


class IntDistributionInfo(pyd.BaseModel):
    """Information describing a discretised three-point random distribution."""

    type: ty.Literal['Constant', 'IntTriangular', 'IntPERT']  # Supported distribution types
    """Type of the distribution."""

    low: pyd.NonNegativeInt
    """Minimum value of the distribution."""

    mode: pyd.NonNegativeInt
    """Most likely value of the distribution, before discretisation."""

    high: pyd.NonNegativeInt
    """Maximum value of the distribution."""

    @pyd.model_validator(mode='after')
    def _enforce_ordering(self) -> 'DistributionInfo':
        """Ensure that the the ``low``, ``mode`` and ``high`` parameters of the distribution
        are in non-decreasing order."""
        # Constant case
        if self.type == 'Constant':
            return __class__.model_construct(
                type='Constant', low=self.mode, mode=self.mode, high=self.mode)
        # Other cases
        assert self.mode >= self.low, 'Failed requirement: mode >= low'
        assert self.high >= self.mode, 'Failed requirement: high >= mode'
        return self


class Globals(pyd.BaseModel):
    """Stores the global variables of a model.

    Field titles should match the corresponding named range in the Excel input file
    and therefore should not contain any spaces or symbols."""

    prob_internal: Probability = pyd.Field(title='ProbInternal')
    """Probability that a specimen comes from an internal source, i.e. one that uses the
    EPIC system."""

    prob_urgent_cancer: Probability = pyd.Field(title='ProbUrgentCancer')
    """Probability that a cancer-pathway specimen has Urgent priority."""

    prob_urgent_non_cancer: Probability = pyd.Field(title='ProbUrgentNonCancer')
    """Probability that a non-cancer-pathway specimen has Urgent priority."""

    prob_priority_cancer: Probability = pyd.Field(title='ProbPriorityCancer')
    """Probability that a cancer-pathway specimen has Priority priority."""

    prob_priority_non_cancer: Probability = pyd.Field(title='ProbPriorityNonCancer')
    """Probability that a non-cancer-pathway specimen has Priority priority."""

    prob_prebook: Probability = pyd.Field(title='ProbPrebook')
    """Probability that a specimen requires pre-booking-in investigation."""

    prob_invest_easy: Probability = pyd.Field(title='ProbInvestEasy')
    """Probability that an internal specimen requires booking-in investigation, and
    the investigation is classified as "easy"."""

    prob_invest_hard: Probability = pyd.Field(title='ProbInvestHard')
    """Probability that an internal specimen requires booking-in investigation, and
    the investigation is classified as "hard"."""

    prob_invest_external: Probability = pyd.Field(title='ProbInvestExternal')
    """Probability that an external specimen requires booking-in investigation."""

    prob_bms_cutup: Probability = pyd.Field(title='ProbBMSCutup')
    """Probability that a non-urgent specimen goes to BMS cut-up."""

    prob_bms_cutup_urgent: Probability = pyd.Field(title='ProbBMSCutupUrgent')
    """Probability that an urgent specimen goes to BMS cut-up."""

    prob_large_cutup: Probability = pyd.Field(title='ProbLargeCutup')
    """Probability that a non-urgent specimen goes to large specimens cut-up."""

    prob_large_cutup_urgent: Probability = pyd.Field(title='ProbLargeCutupUrgent')
    """Probability that an urgent specimen goes to large specimens cut-up."""

    prob_pool_cutup: Probability = pyd.Field(title='ProbPoolCutup')
    """Probability that a non-urgent specimen goes to Pool cut-up."""

    prob_pool_cutup_urgent: Probability = pyd.Field(title='ProbPoolCutupUrgent')
    """Probability that an urgent specimen goes to Pool cut-up."""

    prob_mega_blocks: Probability = pyd.Field(title='ProbMegaBlocks')
    """Probability that a large specimen cut-up produces mega blocks. With the remaining
    probability, large surgical blocks are produced instead."""

    prob_decalc_bone: Probability = pyd.Field(title='ProbDecalcBone')
    """Probability that an specimen requires decalcification at a bone station."""

    prob_decalc_oven: Probability = pyd.Field(title='ProbDecalcOven')
    """Probability that an specimen requires decalcification in a decalc oven."""

    prob_microtomy_levels: Probability = pyd.Field(title='ProbMicrotomyLevels')
    """Probability that a small surgical block produces a "levels" microtomy task.
    With remaining probability, a "serials" microtomy task is produced."""

    num_blocks_large_surgical: IntDistributionInfo =\
        pyd.Field(title='NumBlocksLargeSurgical')
    """Parameters for the number of large surgical blocks produced in a cut-up that produces
    such blocks."""

    num_blocks_mega: IntDistributionInfo = pyd.Field(title='NumBlocksMega')
    """Parameters for the number of mega blocks produced in a cut-up that produces such blocks."""

    num_slides_larges: IntDistributionInfo = pyd.Field(title='NumSlidesLarges')
    """Parameters for the number of slides produced for a large surgical microtomy task."""

    num_slides_levels: IntDistributionInfo = pyd.Field(title='NumSlidesLarges')
    """Parameters for the number of slides produced for a levels microtomy task."""

    num_slides_megas: IntDistributionInfo = pyd.Field(title='NumSlidesLarges')
    """Parameters for the number of slides produced for a megas microtomy task."""

    num_slides_serials: IntDistributionInfo = pyd.Field(title='NumSlidesLarges')
    """Parameters for the number of slides produced for a serials microtomy task."""


class MockCounts(pyd.BaseModel):
    """Stores the initial number of mock specimens for the simulation model when
    `Config.opt_initial_specimens` is `'mock'`."""

    reception_cancer: pyd.NonNegativeInt = pyd.Field(title='Reception (cancer)')
    reception_noncancer: pyd.NonNegativeInt = pyd.Field(title='Reception (non-cancer)')
    cutup_cancer: pyd.NonNegativeInt = pyd.Field(title='Cut-up (cancer)')
    cutup_noncancer: pyd.NonNegativeInt = pyd.Field(title='Cut-up (non-cancer)')
    processing_cancer: pyd.NonNegativeInt = pyd.Field(title='Processing (cancer)')
    processing_noncancer: pyd.NonNegativeInt = pyd.Field(title='Processing (non-cancer)')
    microtomy_cancer: pyd.NonNegativeInt = pyd.Field(title='Microtomy (cancer)')
    microtomy_noncancer: pyd.NonNegativeInt = pyd.Field(title='Microtomy (non-cancer)')
    staining_cancer: pyd.NonNegativeInt = pyd.Field(title='Staining (cancer)')
    staining_noncancer: pyd.NonNegativeInt = pyd.Field(title='Staining (non-cancer)')
    labelling_cancer: pyd.NonNegativeInt = pyd.Field(title='Labelling (cancer)')
    labelling_noncancer: pyd.NonNegativeInt = pyd.Field(title='Labelling (non-cancer)')
    scanning_cancer: pyd.NonNegativeInt = pyd.Field(title='Scanning (cancer)')
    scanning_noncancer: pyd.NonNegativeInt = pyd.Field(title='Scanning (non-cancer)')
    qc_cancer: pyd.NonNegativeInt = pyd.Field(title='QC (cancer)')
    qc_noncancer: pyd.NonNegativeInt = pyd.Field(title='QC (non-cancer)')
    reporting_cancer: pyd.NonNegativeInt = pyd.Field(title='Reporting (cancer)')
    reporting_noncancer: pyd.NonNegativeInt = pyd.Field(title='Reporting (non-cancer)')


class RunnerTimeRow(pyd.BaseModel):
    """Represents a row in the weighted adjaceny matrix containing travel times (in seconds)
    between histopathology locations."""
    model_config = pyd.ConfigDict(populate_by_name=True)

    specimen_reception: pyd.NonNegativeFloat = pyd.Field(alias='Specimen Reception')
    lilac_room: pyd.NonNegativeFloat = pyd.Field(alias='Lilac Room')
    white_room: pyd.NonNegativeFloat = pyd.Field(alias='White Room')
    yellow_room: pyd.NonNegativeFloat = pyd.Field(alias='Yellow Room')
    green_room: pyd.NonNegativeFloat = pyd.Field(alias='Green Room')
    processing_room: pyd.NonNegativeFloat = pyd.Field(alias='Processing Room')
    first_floor_corridor_d7: pyd.NonNegativeFloat = pyd.Field(alias='First Floor Corridor D7')
    main_lab: pyd.NonNegativeFloat = pyd.Field(alias='Main Lab')
    staining_room: pyd.NonNegativeFloat = pyd.Field(alias='Staining Room')
    second_floor_landing: pyd.NonNegativeFloat = pyd.Field(alias='Second Floor Landing')
    second_floor_lift_door: pyd.NonNegativeFloat = pyd.Field(alias='Second Floor Lift Door')
    first_floor_landing: pyd.NonNegativeFloat = pyd.Field(alias='First Floor Landing')
    first_floor_lift_door: pyd.NonNegativeFloat = pyd.Field(alias='First Floor Lift Door')
    first_floor_corridor_d14: pyd.NonNegativeFloat = pyd.Field(alias='First Floor Corridor D14')
    first_floor_corridor_d15: pyd.NonNegativeFloat = pyd.Field(alias='First Floor Corridor D15')
    digital_pathology: pyd.NonNegativeFloat = pyd.Field(alias='Digital Pathology')

class RunnerTimes(pyd.BaseModel):
    """Represents a matrix of travel times between histopathology locations."""
    model_config = pyd.ConfigDict(populate_by_name=True)

    specimen_reception: RunnerTimeRow = pyd.Field(alias='Specimen Reception')
    lilac_room: RunnerTimeRow = pyd.Field(alias='Lilac Room')
    white_room: RunnerTimeRow = pyd.Field(alias='White Room')
    yellow_room: RunnerTimeRow = pyd.Field(alias='Yellow Room')
    green_room: RunnerTimeRow = pyd.Field(alias='Green Room')
    processing_room: RunnerTimeRow = pyd.Field(alias='Processing Room')
    first_floor_corridor_d7: RunnerTimeRow = pyd.Field(alias='First Floor Corridor D7')
    main_lab: RunnerTimeRow = pyd.Field(alias='Main Lab')
    staining_room: RunnerTimeRow = pyd.Field(alias='Staining Room')
    second_floor_landing: RunnerTimeRow = pyd.Field(alias='Second Floor Landing')
    second_floor_lift_door: RunnerTimeRow = pyd.Field(alias='Second Floor Lift Door')
    first_floor_landing: RunnerTimeRow = pyd.Field(alias='First Floor Landing')
    first_floor_lift_door: RunnerTimeRow = pyd.Field(alias='First Floor Lift Door')
    first_floor_corridor_d14: RunnerTimeRow = pyd.Field(alias='First Floor Corridor D14')
    first_floor_corridor_d15: RunnerTimeRow = pyd.Field(alias='First Floor Corridor D15')
    digital_pathology: RunnerTimeRow = pyd.Field(alias='Digital Pathology')


class Config(pyd.BaseModel):
    """Configuration settings for the histopathlogy department model."""

    arrival_schedules: ArrivalSchedules = pyd.Field(title='Arrival Schedules')
    """Arrival schedules for cancer and non-cancer specimens."""

    resources_info: ResourcesInfo = pyd.Field(title='Resources')
    """Allocation schedules for each resource."""

    task_durations_info: TaskDurationsInfo = pyd.Field(title='Task Durations')
    """Task duration distribution parameters."""

    batch_sizes: BatchSizes = pyd.Field(title='Batch Sizes')
    """Batch sizes for various machine and delivery tasks."""

    global_vars: Globals = pyd.Field(title='Global Variables')
    """Miscellaneous model-wide parameters."""

    sim_hours: pyd.NonNegativeFloat = pyd.Field(title='Simulation length (hours)')
    """The simulation length in hours."""

    num_reps: pyd.NonNegativeInt = pyd.Field(title='Number of simulation replications')
    """Number of simulation replications to run."""

    # TODO: add 'from_file' option for reading initial specimen data from file
    opt_initial_specimens: ty.Literal['mock', 'none']\
        = pyd.Field(title='Bootstrap initial state')
    """Option to bootstrap the simulation startup state using either dynamically generated
    mock specimens or specimen data from the config file."""

    mock_counts: ty.Optional[MockCounts] = pyd.Field(title='Mock Specimen Counts')
    """Mock specimen counts, used when `opt_initial_specimens` is 'from_file'."""

    opt_runner_times: bool = pyd.Field(title='Use travel times')
    """Option to read travel time between locations from file."""

    runner_times: ty.Optional[RunnerTimes] = pyd.Field(title='Travel times')
    """Travel time between locations in the histopathology department."""

    @staticmethod
    def from_workbook(
        # path: os.PathLike,
        wbook: xl.Workbook,
        sim_hours: float,
        num_reps: int,
    ) -> 'Config':
        """Load a config from an Excel workbook."""
        # wbook = xl.load_workbook(path, data_only=True)

        # ARRIVAL SCHEDULES

        arrival_schedule_cancer_df = xlh.get_table(
            wbook, sheet_name='Arrival Schedules', name='ArrivalScheduleCancer'
        ).set_index('Hour')
        arrival_schedule_cancer_df =\
            arrival_schedule_cancer_df[arrival_schedule_cancer_df.index != 'Total']\
            # pylint:disable=E1136

        arrival_schedule_noncancer_df = xlh.get_table(
            wbook, sheet_name='Arrival Schedules', name='ArrivalScheduleNonCancer'
        ).set_index('Hour')
        arrival_schedule_noncancer_df =\
            arrival_schedule_noncancer_df[arrival_schedule_noncancer_df.index != 'Total']\
            # pylint:disable=E1136

        arrival_schedules = ArrivalSchedules(
            cancer=ArrivalSchedule.from_pd(arrival_schedule_cancer_df),
            noncancer=ArrivalSchedule.from_pd(arrival_schedule_noncancer_df)
        )

        # RESOURCES

        resources_df = xlh.get_table(
            wbook, sheet_name='Resource Allocation', name='Resources')\
            .fillna(0.0).set_index('Resource')
        resources_info = {key: ResourceInfo(
            name=field.title,
            type=field.json_schema_extra['resource_type'],
            schedule=ResourceSchedule.from_pd(resources_df, row_name=field.title)
        ) for key, field in ResourcesInfo.model_fields.items()}
        resources_info = ResourcesInfo(**resources_info)

        # TASK DURATIONS

        tasks_df = xlh.get_table(
            wbook, sheet_name='Task Durations', name='TaskDurations').set_index('Task')
        task_durations_info = {key: DistributionInfo(
            type=tasks_df.loc[field.title, 'Distribution'],
            low=tasks_df.loc[field.title, 'Optimistic'],
            mode=tasks_df.loc[field.title, 'Most Likely'],
            high=tasks_df.loc[field.title, 'Pessimistic'],
            time_unit=tasks_df.loc[field.title, 'Units'],
        ) for key, field in TaskDurationsInfo.model_fields.items()}
        task_durations_info = TaskDurationsInfo(**task_durations_info)

        # BATCH SIZES

        batch_sizes_df = xlh.get_table(
            wbook, sheet_name='Batch Sizes', name='BatchSizes').set_index('Batch Name')
        batch_sizes = {key: batch_sizes_df.loc[field.title, 'Size']
                       for key, field in BatchSizes.model_fields.items()}

        # GLOBAL PARAMETERS

        globals_float = {
            key: xlh.get_name(wbook, field.title) for key, field in Globals.model_fields.items()
            if field.annotation == float
        }
        globals_dists = {
            key: IntDistributionInfo(
                type=xlh.get_name(wbook, field.title)[0],
                low=xlh.get_name(wbook, field.title)[1],
                mode=xlh.get_name(wbook, field.title)[2],
                high=xlh.get_name(wbook, field.title)[3]
            )
            for key, field in Globals.model_fields.items()
            if field.annotation == IntDistributionInfo
        }
        global_vars = Globals(**globals_float, **globals_dists)

        # OPTION: INITIAL SPECIMENS

        opt_initial_specimens = xlh.get_name(wbook, name='OptSpecimenBootstrap')
        opt_initial_specimens = (
            'mock' if opt_initial_specimens == 'Yes'
            else 'none'
        )

        # INITIAL SPECIMENS (MOCK)

        if opt_initial_specimens == 'mock':
            mock_counts_df = xlh.get_table(
                wbook, sheet_name='Bootstrap Mock Generator', name='MockCounts').set_index('Stage')
            mock_counts = {}
            for key, field in MockCounts.model_fields.items():
                row_name, col = field.title.rsplit(' ', 1)
                col_name = 'Cancer' if col == '(cancer)' else 'NonCancer'
                mock_counts[key] = mock_counts_df.loc[row_name, col_name]
            mock_counts = MockCounts(**mock_counts)
        else:
            mock_counts = None
        
        # OPTION: RUNNER TIMES

        opt_travel_times = xlh.get_name(wbook, name='OptTravelTimes') == 'Yes'

        # RUNNER TIMES
        if opt_travel_times:
            data = xlh.get_named_matrix(wbook, index_name='LocationNames', data_name='RunnerTimes')
            df = pd.DataFrame(data).T
            df.insert(0,'Specimen Reception', float('nan'))
            df.fillna(0, inplace=True)
            runner_times = df + df.T
            g = nx.from_pandas_adjacency(runner_times)
            runner_times = RunnerTimes(**dict(nx.shortest_path_length(g, weight='weight')))
        else:
            runner_times = None


        # Call __init__()
        return Config(
            arrival_schedules=arrival_schedules,
            resources_info=resources_info,
            task_durations_info=task_durations_info,
            batch_sizes=batch_sizes,
            global_vars=global_vars,
            opt_initial_specimens=opt_initial_specimens,
            mock_counts=mock_counts,
            opt_runner_times = opt_travel_times,
            runner_times=runner_times,
            sim_hours=sim_hours,
            num_reps=num_reps
        )
