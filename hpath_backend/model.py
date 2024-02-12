"""The histopathology simulation model.

Separating the Model class from the Config class
is necessary for our backend as the Model class is
not serialisable by the RQ (Redis job queue) module.
"""
import dataclasses
from dataclasses import dataclass
from typing import Literal

import dacite
import salabim as sim

from . import process
from .config import Config, DistributionInfo, IntDistributionInfo, ResourceInfo
from .distributions import PERT, Constant, Distribution, IntPERT, Tri
from .mock_specimens import InitSpecimen
from .process import ArrivalGenerator, ProcessType, ResourceScheduler
from .util import dc_items


@dataclass(kw_only=True, eq=False)
class Resources:
    """Dataclass for tracking the resources of a :py:class:`Model`.

    See also:
        :py:class:`hpath_backend.config.ResourcesInfo`
    """

    booking_in_staff: sim.Resource
    bms: sim.Resource
    cut_up_assistant: sim.Resource
    processing_room_staff: sim.Resource
    microtomy_staff: sim.Resource
    staining_staff: sim.Resource
    scanning_staff: sim.Resource
    qc_staff: sim.Resource
    histopathologist: sim.Resource
    bone_station: sim.Resource
    processing_machine: sim.Resource
    staining_machine: sim.Resource
    coverslip_machine: sim.Resource
    scanning_machine_regular: sim.Resource
    scanning_machine_megas: sim.Resource

    def __init__(self, env: 'Model') -> None:
        for _field in dataclasses.fields(__class__):
            self.__setattr__(
                _field.name,
                sim.Resource(env=env)
            )


@dataclass(kw_only=True, eq=False)
class TaskDurations:
    """Dataclass for tracking task durations in a :py:class:`Model`.

    See also:
        :py:class:`hpath_backend.config.TaskDurationsInfo`
    """
    receive_and_sort: Distribution
    pre_booking_in_investigation: Distribution
    booking_in_internal: Distribution
    booking_in_external: Distribution
    booking_in_investigation_internal_easy: Distribution
    booking_in_investigation_internal_hard: Distribution
    booking_in_investigation_external: Distribution
    cut_up_bms: Distribution
    cut_up_pool: Distribution
    cut_up_large_specimens:  Distribution
    load_bone_station: Distribution
    decalc: Distribution
    unload_bone_station: Distribution
    load_into_decalc_oven: Distribution
    unload_from_decalc_oven: Distribution
    load_processing_machine: Distribution
    unload_processing_machine: Distribution
    processing_urgent: Distribution
    processing_small_surgicals: Distribution
    processing_large_surgicals: Distribution
    processing_megas: Distribution
    embedding: Distribution
    embedding_cooldown: Distribution
    block_trimming: Distribution
    microtomy_serials: Distribution
    microtomy_levels: Distribution
    microtomy_larges: Distribution
    microtomy_megas: Distribution
    load_staining_machine_regular: Distribution
    load_staining_machine_megas: Distribution
    staining_regular: Distribution
    staining_megas: Distribution
    unload_staining_machine_regular: Distribution
    unload_staining_machine_megas: Distribution
    load_coverslip_machine_regular: Distribution
    coverslip_regular: Distribution
    coverslip_megas: Distribution
    unload_coverslip_machine_regular: Distribution
    labelling: Distribution
    load_scanning_machine_regular: Distribution
    load_scanning_machine_megas: Distribution
    scanning_regular: Distribution
    scanning_megas: Distribution
    unload_scanning_machine_regular: Distribution
    unload_scanning_machine_megas: Distribution
    block_and_quality_check: Distribution
    assign_histopathologist: Distribution
    write_report: Distribution


@dataclass(kw_only=True)
class Wips:
    """Dataclass for tracking work-in-progress counters for the :py:class:`Model` simulation."""
    total: sim.Monitor
    in_reception: sim.Monitor
    in_cut_up: sim.Monitor
    in_processing: sim.Monitor
    in_microtomy: sim.Monitor
    in_staining: sim.Monitor
    in_labelling: sim.Monitor
    in_scanning: sim.Monitor
    in_qc: sim.Monitor
    in_reporting: sim.Monitor

    def __init__(self, env: sim.Environment) -> None:
        self.total = sim.Monitor('Total WIP', level=True, type="uint32", env=env)
        self.in_reception = sim.Monitor('Reception', level=True, type="uint32", env=env)
        self.in_cut_up = sim.Monitor('Cut-up', level=True, type="uint32", env=env)
        self.in_processing = sim.Monitor('Processing', level=True, type="uint32", env=env)
        self.in_microtomy = sim.Monitor('Microtomy', level=True, type="uint32", env=env)
        self.in_staining = sim.Monitor('Staining', level=True, type="uint32", env=env)
        self.in_labelling = sim.Monitor('Labelling', level=True, type="uint32", env=env)
        self.in_scanning = sim.Monitor('Scanning', level=True, type="uint32", env=env)
        self.in_qc = sim.Monitor('QC', level=True, type="uint32", env=env)
        self.in_reporting = sim.Monitor('Reporting stage', level=True, type="uint32", env=env)


class Model(sim.Environment):
    """The simulation model.

    **Note**: during initialisation from a :py:class:`hpath_backend.config.Config` object,
    distribution parameters are converted into actual distribution instances from the
    :py:mod:`hpath_backend.distributions` module.

    Attributes:
        num_reps (int):
            The number of simulation replications to run the model.
        sim_length (float):
            The duration of each simulation replication.
        created (float):
            UNIX timestamp of the model configuration's creation time.
        analysis_id (int | None):
            ID of the multi-scenario analysis, if this model is part of one.
        resources (Resources):
            The resources associated with this model, as a dataclass instance.
        task_durations:
            Dataclass instance containing the task durations for the model.
        batch_sizes (hpath.config.BatchSizes):
            Dataclass instance containing the batch sizes for various tasks in the model.
        globals (hpath.config.Globals)
            Dataclass instance containing global variables for the model.
        completed_specimens (salabim.Store):
            A store containing completed specimens, so that statistics can be computed.
        wips (Wips):
            Dataclass instance containing work-in-progress counters for the model.
        processes (dict[str, hpath.process.Process |
        hpath.process.BatchingProcess | hpath.process.CollationProcess]):
            Dict mapping strings to the processes of the simulation model.
    """

    def __init__(self, config: Config, **kwargs) -> None:
        """Constructor.

        Args:
            config (hpath.config.Config):
                Configuration settings for the simulation model.
            kwargs:
                Additional parameters absorbed by the super() constructor.
        """

        # Change super() defaults
        kwargs['time_unit'] = kwargs.get('time_unit', 'hours')
        kwargs['random_seed'] = kwargs.get('random_seed', '*')
        super().__init__(**kwargs, config=config)

    def setup(self, config: Config) -> None:  # pylint: disable=arguments-differ
        super().setup()

        self.num_reps: int = config.num_reps
        self.sim_length: float = self.env.hours(config.sim_hours)

        # ARRIVALS
        ArrivalGenerator(
            'Arrival Generator (cancer)',
            schedule=config.arrival_schedules.cancer,
            env=self,
            # cls_args for Specimen() below
            cancer=True
        )
        ArrivalGenerator(
            'Arrival Generator (non-cancer)',
            schedule=config.arrival_schedules.cancer,
            env=self,
            # cls_args for Specimen() below
            cancer=False
        )

        # RESOURCES AND RESOURCE SCHEDULERS
        self.resources = Resources(self)
        for name, resource in dc_items(self.resources):
            resource: sim.Resource
            resource_info: ResourceInfo = getattr(config.resources_info, name)
            resource.name(resource_info.name)  # Assign user-friendly resource name

            # Associate new scheduler with resource
            ResourceScheduler(
                f'Scheduler [{resource.name()}]',
                resource=resource,
                schedule=resource_info.schedule,
                env=self
            )

        # TASK DURATIONS
        # DistributionInfo is set up so that only the first letter is used for `time_unit`

        def time_unit_full(abbr: Literal['s', 'm', 'h']):
            return "seconds" if abbr == 's' else "minutes" if abbr == 'm' else "hours"

        task_durations = {}
        for key, val in iter(config.task_durations_info):
            val: DistributionInfo
            task_durations[key] = (
                PERT(val.low, val.mode, val.high, time_unit_full(val.time_unit), env=self)
                if val.type == 'PERT' else
                Tri(val.low, val.mode, val.high, time_unit_full(val.time_unit), env=self)
                if val.type == 'Triangular' else
                Constant(val.mode, time_unit_full(val.time_unit), env=self)
            )
        self.task_durations = dacite.from_dict(TaskDurations, task_durations)

        self.batch_sizes = config.batch_sizes

        # GLOBALS
        self.globals = config.global_vars
        # Currently, only the IntPERT distribution is used in self.globals --
        # Convert these to distribution objects
        for key, val in iter(self.globals):
            if isinstance(val, IntDistributionInfo):
                if val.type == 'IntPERT':
                    setattr(self.globals, key, IntPERT(val.low, val.mode, val.high, env=self))
                else:
                    raise ValueError(f'Distribution type {val.type} not (yet) supported.')

        # DATA STORE FOR COMPLETED SPECIMENS
        self.completed_specimens = sim.Store(
            name='Completed specimens',
            env=self
        )

        # SPECIMEN DATA
        self.specimen_data: dict[str, dict] = {}

        # WORK-IN-PROGRESS COUNTERS
        self.wips = Wips(self)

        # REGISTER PROCESSES
        self.processes: dict[str, ProcessType] = {}

        process.p10_reception.register(self)
        process.p20_cutup.register(self)
        process.p30_processing.register(self)
        process.p40_microtomy.register(self)
        process.p50_staining.register(self)
        process.p60_labelling.register(self)
        process.p70_scanning.register(self)
        process.p80_qc.register(self)
        process.p90_reporting.register(self)

        # FREQUENTLY USED DISTRIBUTIONS
        self.u01 = sim.Uniform(0, 1, time_unit=None, env=self)

        # INITIAL SPECIMENS (MOCK)
        stages = ['reception', 'cutup', 'processing', 'microtomy', 'staining',
                  'labelling', 'scanning', 'qc', 'reporting']
        insert_points = [
            'arrive_reception',
            'cutup_start',
            'processing_start',
            'microtomy',
            'staining_start',
            'labelling',
            'scanning_start',
            'qc',
            'assign_histopath'
        ]

        if config.opt_initial_specimens == 'mock':
            init_specimens: list[InitSpecimen] = []
            for idx, stage in enumerate(stages):
                insert_point = insert_points[idx]
                for pathway in ['cancer', 'noncancer']:
                    mock_count = getattr(config.mock_counts, f'{stage}_{pathway}')
                    for _ in range(mock_count):
                        specimen = InitSpecimen(env=self, cancer=pathway == 'cancer')

                        # Generate timestamps
                        for stage2 in stages[:idx]:
                            specimen.preprocess[stage2]()
                        specimen.compute_timestamps()
                        self.specimen_data[specimen.name()]['insert_point'] = insert_point

                        init_specimens.append(specimen)

            # Sort by time
            init_specimens.sort(key=lambda item: 
                                self.specimen_data[item.name()].get('reception_start', self.now()))

            # Insert mock specimens
            for specimen in init_specimens:
                insert_point = self.specimen_data[specimen.name()]['insert_point']
                if insert_point == 'arrive_reception':
                    self.processes[insert_point].in_queue.add(specimen)
                else:
                    self.processes[insert_point].in_queue.add_sorted(specimen, specimen.prio)
                    self.wips.total.value += 1

        # RUNNER TIMES
        self.runner_times = None
        if config.opt_runner_times:
            self.runner_times = config.runner_times

    def run(self) -> None:  # pylint: disable=arguments-differ
        """Run the simulation for the duration set in ``self.sim_length``."""
        super().run(duration=self.sim_length)
