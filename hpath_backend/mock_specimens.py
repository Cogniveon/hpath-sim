"""Mock specimens for bootstrapping the simulation state.
Used for the case where we know the number of specimens waiting
in each stage at the simulation start, but do not have detailed
timestamp information.

In this implementation, we create fake timestamp information based on
sampling the task duration distributions and assuming no queueing delays.
This can be used to compute the **minimum** expected turnaround time of each specimen;
however, mock specimens should be excluded from computing average delay
statistics.
"""

from typing import Callable, Self, TYPE_CHECKING
from hpath_backend.specimens import Priority, Specimen, Block, Slide

if TYPE_CHECKING:
    from hpath_backend.model import Model


class InitSpecimen(Specimen):
    """Special subclass of `Specimen` for specimens already in progress at simulation start."""

    def init_reception(self) -> None:
        """Generate task_durations for specimen that has already completed Reception
        at simulation start."""
        env: 'Model' = self.env

        # Receive and sort
        elapsed_time = env.task_durations.receive_and_sort()

        # Pre-booking-in investigation
        if env.u01() < env.globals.prob_prebook:
            elapsed_time += env.task_durations.pre_booking_in_investigation()

        # Booking-in
        if self.data['source'] == 'Internal':
            elapsed_time += env.task_durations.booking_in_internal()
        else:
            elapsed_time += env.task_durations.booking_in_external()

        # Additional investigation
        if self.data['source'] == 'Internal':
            r = env.u01()
            if r < env.globals.prob_invest_easy:
                elapsed_time += env.task_durations.booking_in_investigation_internal_easy()
            elif r < env.globals.prob_invest_easy + env.globals.prob_invest_hard:
                elapsed_time += env.task_durations.booking_in_investigation_internal_hard()
        elif env.u01() < env.globals.prob_invest_external:
            elapsed_time += env.task_durations.booking_in_investigation_external()

        # End of stage
        self.data['bootstrap']['reception'] = elapsed_time
        self.data['bootstrap']['reception_to_cutup']\
            = env.processes['reception_to_cutup'].out_duration

    def init_cut_up(self) -> None:
        """Generate task_durations for specimen that has already completed Cut-Up
        at simulation start."""
        env: Model = self.env

        r = env.u01()
        suffix = '_urgent' if self.prio == Priority.URGENT else ''
        if r < getattr(env.globals, 'prob_bms_cutup'+suffix):
            self.data["cutup_type"] = 'BMS'

            # One small surgical block
            self.data['num_blocks'] = 1
            self.blocks.append(Block(
                f'{self.name()}.',
                env=env,
                parent=self,
                block_type='small surgical'
            ))
            elapsed_time = env.task_durations.cut_up_bms()

        elif r < (getattr(env.globals, 'prob_bms_cutup'+suffix) +
                  getattr(env.globals, 'prob_pool_cutup'+suffix)):
            self.data["cutup_type"] = 'Pool'

            # One large surgical block
            self.data['num_blocks'] = 1
            self.blocks.append(Block(
                f'{self.name()}.',
                env=env,
                parent=self,
                block_type='large surgical'
            ))
            elapsed_time = env.task_durations.cut_up_pool()

        else:
            self.data["cutup_type"] = 'Large specimens'

            # Urgent cut-ups never produce megas. Other large surgical blocks produce
            # megas with a given probability.
            if (self.prio == Priority.URGENT) or (env.u01() < env.globals.prob_mega_blocks):
                n_blocks = env.globals.num_blocks_mega()
                block_type = 'mega'
            else:
                n_blocks = env.globals.num_blocks_large_surgical()
                block_type = 'large surgical'

            self.data['num_blocks'] = n_blocks
            for _ in range(n_blocks):
                block = Block(
                    f'{self.name()}.',
                    env=env,
                    parent=self,
                    block_type=block_type
                )
                self.blocks.append(block)
            elapsed_time = env.task_durations.cut_up_large_specimens()

        # End of stage
        self.data['bootstrap']['cutup'] = elapsed_time
        self.data['bootstrap']['cutup_to_processing'] = (
            env.processes['cutup_bms_to_processing'].out_duration
            if self.data["cutup_type"] == 'BMS'
            else env.processes['cutup_pool_to_processing'].out_duration
            if self.data["cutup_type"] == 'Pool'
            else env.processes['cutup_large_to_processing'].out_duration
        )
    
    # NOTE: to avoid name clashes with regular Specimen processes (which are added to the
    # Specimen using setattr() in each of the `hpath_backend.process` submodules), we must
    # use a "init_" prefix for the functions below.
    #
    # More specifically, each `hpath_backend.process` submodule calls Process.__init__(),
    # which in turn calls Specimen.setattr().

    def init_processing(self) -> None:
        """Generate task_durations for specimen that has already completed Processing
        at simulation start."""
        env: Model = self.env
        elapsed_time = 0

        # Decalc
        r = env.u01()
        if r < env.globals.prob_decalc_bone:
            self.data['decalc_type'] = 'bone station'
            elapsed_time += (  # Assume no delay; all blocks decalc'ed simultaneously
                env.task_durations.load_bone_station()
                + env.task_durations.decalc()
                + env.task_durations.unload_bone_station()
            )
        elif r < env.globals.prob_decalc_bone + env.globals.prob_decalc_oven:
            self.data['decalc_type'] = 'decalc oven'
            elapsed_time += (  # Assume no delay; all blocks decalc'ed simultaneously
                env.task_durations.load_into_decalc_oven()
                + env.task_durations.decalc()
                + env.task_durations.unload_from_decalc_oven()
            )

        # Main processing
        # Assume no delay; all blocks processed simultaneously.
        # Take advantage of the fact all blocks will be of the same type.
        elapsed_time += env.task_durations.load_processing_machine()
        if self.prio == Priority.URGENT:
            elapsed_time += env.task_durations.processing_urgent()
        elif self.blocks[0].data["block_type"] == "small surgical":
            elapsed_time += env.task_durations.processing_small_surgicals()
        elif self.blocks[0].data["block_type"] == "large surgical":
            elapsed_time += env.task_durations.processing_large_surgicals()
        else:
            elapsed_time += env.task_durations.processing_megas()
        elapsed_time += env.task_durations.unload_processing_machine()

        # End of stage
        self.data['bootstrap']['processing'] = elapsed_time
        self.data['bootstrap']['processing_to_microtomy'] \
            = env.processes['processing_to_microtomy'].out_duration

    def init_microtomy(self) -> None:
        """Generate task_durations for specimen that has already completed Microtomy
        at simulation start."""
        env: Model = self.env

        # Take advantage of the fact all slides will be of the same type
        # Slides are microtomed manually
        # Assume no gaps/delays, total elapsed time will be proportional to the number of blocks
        elapsed_time = 0
        self.data['total_slides'] = 0

        for block in self.blocks:
            if block.data['block_type'] == 'small surgical':
                # Small surgical blocks produce "levels" or "serials" slides
                if env.u01() < env.globals.prob_microtomy_levels:
                    slide_type = 'levels'
                    elapsed_time += env.task_durations.microtomy_levels()
                    num_slides = env.globals.num_slides_levels()
                else:
                    slide_type = 'serials'
                    elapsed_time += env.task_durations.microtomy_serials()
                    num_slides = env.globals.num_slides_serials()
            elif block.data['block_type'] == 'large surgical':
                slide_type = 'larges'
                elapsed_time += env.task_durations.microtomy_larges()
                num_slides = env.globals.num_slides_larges()
            else:
                slide_type = 'megas'
                elapsed_time += env.task_durations.microtomy_megas()
                num_slides = env.globals.num_slides_megas()

            for _ in range(num_slides):
                slide = Slide(
                    f'{block.name()}.',
                    env=env,
                    parent=block,
                    slide_type=slide_type
                )
                block.slides.append(slide)
            block.data['num_slides'] = num_slides
            self.data['total_slides'] += num_slides

        # End of stage
        self.data['bootstrap']['microtomy'] = elapsed_time
        self.data['bootstrap']['microtomy_to_staining'] \
            = env.processes['microtomy_to_staining'].out_duration

    def init_staining(self) -> None:
        """Generate task_durations for specimen that has already completed Staining
        at simulation start."""
        env: Model = self.env

        # Take advantage of the fact all slides will be of the same type
        # Assume all slides can be stained at the same time, with no delays
        slides_type = self.blocks[0].slides[0].data['slide_type']
        if slides_type == 'megas':
            elapsed_time = env.task_durations.load_staining_machine_megas()
            elapsed_time += env.task_durations.staining_megas()
            elapsed_time += env.task_durations.unload_staining_machine_megas()
            # mega slides are coverslipped individually
            for block in self.blocks:
                for _ in block.slides:
                    elapsed_time += env.task_durations.coverslip_megas()
        else:
            elapsed_time = env.task_durations.load_staining_machine_regular()
            elapsed_time += env.task_durations.staining_regular()
            elapsed_time += env.task_durations.unload_staining_machine_regular()
            elapsed_time += env.task_durations.load_coverslip_machine_regular()
            elapsed_time += env.task_durations.coverslip_regular()
            elapsed_time += env.task_durations.unload_coverslip_machine_regular()

        # End of stage
        self.data['bootstrap']['staining'] = elapsed_time
        self.data['bootstrap']['staining_to_labelling'] \
            = env.processes['staining_to_labelling'].out_duration

    def init_labelling(self) -> None:
        """Generate task_durations for specimen that has already completed Labelling
        at simulation start."""
        env: Model = self.env

        # Slides are labelled individually
        elapsed_time = 0
        for block in self.blocks:
            for _ in block.slides:
                elapsed_time += env.task_durations.labelling()

        # End of stage
        self.data['bootstrap']['labelling'] = elapsed_time
        self.data['bootstrap']['labelling_to_scanning'] \
            = env.processes['labelling_to_scanning'].out_duration

    def init_scanning(self) -> None:
        """Generate task_durations for specimen that has already completed Scanning
        at simulation start."""
        env: Model = self.env

        # Assume all slides are scanned together
        slides_type = self.blocks[0].slides[0].data['slide_type']
        if slides_type == 'megas':
            elapsed_time = env.task_durations.load_scanning_machine_megas()
            elapsed_time += env.task_durations.scanning_megas()
            elapsed_time += env.task_durations.unload_scanning_machine_megas()
        else:
            elapsed_time = env.task_durations.load_scanning_machine_regular()
            elapsed_time += env.task_durations.scanning_regular()
            elapsed_time += env.task_durations.unload_scanning_machine_regular()

        # End of stage
        self.data['bootstrap']['scanning'] = elapsed_time
        self.data['bootstrap']['scanning_to_qc'] \
            = env.processes['scanning_to_qc'].out_duration

    def init_qc(self) -> None:
        """Generate task_durations for specimen that has already completed QC
        at simulation start."""
        env: Model = self.env
        self.data['bootstrap']['qc'] = env.task_durations.block_and_quality_check()
        # Since scans are digital, no need for physical delivery to histopathologist

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.insert_point = kwargs.get('insert_point', 'arrive_reception')
        self.data['bootstrap']: dict[str, float] = {}
        self.preprocess: dict[str, Callable[[Self], None]] = {
            'reception': self.init_reception,
            'cutup': self.init_cut_up,
            'processing': self.init_processing,
            'microtomy': self.init_microtomy,
            'staining': self.init_staining,
            'labelling': self.init_labelling,
            'scanning': self.init_scanning,
            'qc': self.init_qc
        }

    def compute_timestamps(self) -> None:
        """Compute mock timestamps for the specimen. These are based on the assumption of no
        delays and provide a minimum possible turnaround time for the mock specimen."""
        timestamp = 0
        if 'qc' in self.data['bootstrap']:
            self.data['qc_end'] = timestamp
            timestamp -= self.data['bootstrap']['qc']
            self.data['qc_start'] = timestamp
        if 'scanning' in self.data['bootstrap']:
            timestamp -= self.data['bootstrap']['scanning_to_qc']
            self.data['scanning_end'] = timestamp
            timestamp -= self.data['bootstrap']['scanning']
            self.data['scanning_start'] = timestamp
        if 'labelling' in self.data['bootstrap']:
            timestamp -= self.data['bootstrap']['labelling_to_scanning']
            self.data['labelling_end'] = timestamp
            timestamp -= self.data['bootstrap']['labelling']
            self.data['labelling_start'] = timestamp
        if 'staining' in self.data['bootstrap']:
            timestamp -= self.data['bootstrap']['staining_to_labelling']
            self.data['staining_end'] = timestamp
            timestamp -= self.data['bootstrap']['staining']
            self.data['staining_start'] = timestamp
        if 'microtomy' in self.data['bootstrap']:
            timestamp -= self.data['bootstrap']['microtomy_to_staining']
            self.data['microtomy_end'] = timestamp
            timestamp -= self.data['bootstrap']['microtomy']
            self.data['microtomy_start'] = timestamp
        if 'processing' in self.data['bootstrap']:
            timestamp -= self.data['bootstrap']['processing_to_microtomy']
            self.data['processing_end'] = timestamp
            timestamp -= self.data['bootstrap']['processing']
            self.data['processing_start'] = timestamp
        if 'cutup' in self.data['bootstrap']:
            timestamp -= self.data['bootstrap']['cutup_to_processing']
            self.data['cutup_end'] = timestamp
            timestamp -= self.data['bootstrap']['cutup']
            self.data['cutup_start'] = timestamp
        if 'reception' in self.data['bootstrap']:
            timestamp -= self.data['bootstrap']['reception_to_cutup']
            self.data['reception_end'] = timestamp
            timestamp -= self.data['bootstrap']['reception']
            self.data['reception_start'] = timestamp
        # else, specimen is waiting to start reception and will be assigned a 'reception_start'
        # timestamp of 0 when the simulation starts

    def process(self) -> None:
        """Overrides `super().process` as we will insert the specimen into the simulation model
        manually.  Does nothing."""
