from ..profiler import Timer,Profiler

import logging
logger = logging.getLogger(__name__)

# zero approximation to avoid zero division exception
APPROX_ZERO = 0.000001

def safe_division(dividend, divisor):
    """Safe division of dividend by operand
    :param number dividend: upper operand of the division
    :param number divisor: lower operand of the division, may be zero
    :return: safe value after division of approximated zero
    """
    try:
        return dividend / divisor
    except (ZeroDivisionError, ValueError):
        return dividend / APPROX_ZERO

class Statistic:
    """General computation stats."""

    # parameters
    status_period = 3
    print_profiling = False

    
    def __init__(self, sketch, synthesizer):
        
        self.synthesizer = synthesizer
        self.sketch = sketch

        self.iterations_dtmc = 0
        self.acc_size_dtmc = 0
        self.avg_size_dtmc = 0

        self.iterations_mdp = 0
        self.acc_size_mdp = 0
        self.avg_size_mdp = 0

        self.feasible = None
        self.assignment = None

        self.synthesis_time = Timer()
        self.status_horizon = Statistic.status_period


    def start(self):
        self.synthesis_time.start()

    
    def iteration_dtmc(self, size_dtmc):
        self.iterations_dtmc += 1
        self.acc_size_dtmc += size_dtmc
        self.print_status()

    def iteration_mdp(self, size_mdp):
        self.iterations_mdp += 1
        self.acc_size_mdp += size_mdp
        self.print_status()

    
    def status(self):
        fraction_rejected = (self.synthesizer.explored + self.synthesizer.sketch.quotient.discarded) / self.sketch.design_space.size
        time_estimate = safe_division(self.synthesis_time.read(), fraction_rejected)
        percentage_rejected = int(fraction_rejected * 1000000) / 10000.0
        # percentage_rejected = fraction_rejected * 100
        time_elapsed = round(self.synthesis_time.read(),1)
        time_estimate = round(time_estimate,1)
        iters = (self.iterations_mdp,self.iterations_dtmc)
        avg_size_mdp = safe_division(self.acc_size_mdp, self.iterations_mdp)
        
        # sat_size = "-"
        # ds = self.synthesizer.sketch.design_space
        # if ds.use_cvc:
        #     sat_size = len(ds.solver.getAssertions())
        # elif ds.use_python_z3:
        #     sat_size = len(ds.solver.assertions())

        return f"> Progress {percentage_rejected}%, elapsed {time_elapsed} s, iters = {iters}"

    def print_status(self):
        if not self.synthesis_time.read() > self.status_horizon:
            return

        if Statistic.print_profiling:
            Profiler.print_all()
        print(self.status(), flush=True)
        self.status_horizon += Statistic.status_period


    def finished(self, assignment):

        self.synthesis_time.stop()
        self.feasible = False
        self.assignment = None
        if assignment is not None:
            self.feasible = True
            self.assignment = str(assignment)

        self.avg_size_dtmc = safe_division(self.acc_size_dtmc, self.iterations_dtmc)
        self.avg_size_mdp = safe_division(self.acc_size_mdp, self.iterations_mdp)

    def get_summary(self):
        spec = self.sketch.specification
        specification = "\n".join([f"constraint {i + 1}: {str(f)}" for i,f in enumerate(spec.constraints)]) + "\n"

        fraction_explored = int((self.synthesizer.explored / self.sketch.design_space.size) * 100)
        explored = f"explored: {fraction_explored} %"

        super_quotient_states = self.sketch.quotient.quotient_mdp.nr_states
        super_quotient_actions = self.sketch.quotient.quotient_mdp.nr_choices

        design_space = f"number of holes: {self.sketch.design_space.num_holes}, family size: {self.sketch.design_space.size}, super quotient: {super_quotient_states} states / {super_quotient_actions} actions"
        timing = f"method: {self.synthesizer.method_name}, synthesis time: {round(self.synthesis_time.time, 2)} s"

        family_stats = ""
        ar_stats = f"AR stats: avg MDP size: {round(self.avg_size_mdp)}, iterations: {self.iterations_mdp}" 
        cegis_stats = f"CEGIS stats: avg DTMC size: {round(self.avg_size_dtmc)}, iterations: {self.iterations_dtmc}"
        if self.iterations_mdp > 0:
            family_stats += f"{ar_stats}\n"
        if self.iterations_dtmc > 0:
            family_stats += f"{cegis_stats}\n"

        feasible = "yes" if self.feasible else "no"
        result = f"feasible: {feasible}"
        # assignment = f"hole assignment: {str(self.assignment)}\n" if self.assignment else ""
        assignment = ""

        sep = "--------------------\n"
        summary = f"{sep}Synthesis summary\n" \
                f"{specification}\n{timing}\n{design_space}\n{explored}\n" \
                f"{family_stats}\n{result}\n{assignment}" \
                f"{sep}"
        return summary

    
    def print(self):    
        if Statistic.print_profiling:
            Profiler.print_all()
        print(self.get_summary())
