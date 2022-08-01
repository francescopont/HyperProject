import stormpy

from ..sketch.spec import *
from ..profiler import Profiler

from collections import OrderedDict

class MarkovChain:

    # options for the construction of chains
    builder_options = None
    # model checking environment (method & precision)
    environment = None

    @classmethod
    def initialize(cls, formulae):
        # builder options
        cls.builder_options = stormpy.BuilderOptions(formulae)
        cls.builder_options.set_build_with_choice_origins(True)
        cls.builder_options.set_build_state_valuations(True)
        cls.builder_options.set_add_overlapping_guards_label()
    
        # model checking environment
        cls.environment = stormpy.Environment()
        
        se = cls.environment.solver_environment

        se.set_linear_equation_solver_type(stormpy.EquationSolverType.gmmxx)
        se.minmax_solver_environment.precision = stormpy.Rational(Specification.mc_precision)
        # se.minmax_solver_environment.method = stormpy.MinMaxMethod.policy_iteration
        se.minmax_solver_environment.method = stormpy.MinMaxMethod.value_iteration
        # se.minmax_solver_environment.method = stormpy.MinMaxMethod.sound_value_iteration
        # se.minmax_solver_environment.method = stormpy.MinMaxMethod.interval_iteration
        # se.minmax_solver_environment.method = stormpy.MinMaxMethod.optimistic_value_iteration
        # se.minmax_solver_environment.method = stormpy.MinMaxMethod.topological

    def __init__(self, model, quotient_container, quotient_state_map, quotient_choice_map):
        Profiler.start("models::MarkovChain")
        if model.labeling.contains_label("overlap_guards"):
            assert model.labeling.get_states("overlap_guards").number_of_set_bits() == 0
        self.model = model
        self.quotient_container = quotient_container
        self.quotient_choice_map = quotient_choice_map
        self.quotient_state_map = quotient_state_map

        # map choices to their origin states
        self.choice_to_state = []
        tm = model.transition_matrix
        for state in range(model.nr_states):
            for choice in range(tm.get_row_group_start(state),tm.get_row_group_end(state)):
                self.choice_to_state.append(state)

        # identify simple holes
        tm = self.model.transition_matrix
        design_space = self.quotient_container.sketch.design_space
        hole_to_states = [0 for hole in design_space]
        for state in range(self.states):
            for hole in quotient_container.state_to_holes[self.quotient_state_map[state]]:
                hole_to_states[hole] += 1
        self.hole_simple = [hole_to_states[hole] == 1 for hole in design_space.hole_indices]

        self.analysis_hints = None
        Profiler.resume()
    
    @property
    def states(self):
        return self.model.nr_states

    @property
    def choices(self):
        return self.model.nr_choices

    @property
    def is_dtmc(self):
        return self.model.nr_choices == self.model.nr_states

    @property
    def initial_states(self):
        return self.model.initial_states

    def model_check_formula(self, formula):
        result = stormpy.model_checking(
            self.model, formula, only_initial_states=False,
            extract_scheduler=(not self.is_dtmc),
            # extract_scheduler=True,
            environment=self.environment
        )
        assert result is not None
        return result

    def model_check_formula_hint(self, formula, hint):
        stormpy.synthesis.set_loglevel_off()
        task = stormpy.core.CheckTask(formula, only_initial_states=False)
        task.set_produce_schedulers(produce_schedulers=True)
        result = stormpy.synthesis.model_check_with_hint(self.model, task, self.environment, hint)
        return result

    def model_check_property(self, prop, alt=False):
        direction = "prim" if not alt else "seco"
        Profiler.start(f"  MC {direction}")
        # get hint
        hint = None
        if self.analysis_hints is not None:
            hint_prim,hint_seco = self.analysis_hints[prop]
            hint = hint_prim if not alt else hint_seco
            # hint = self.analysis_hints[prop]

        formula = prop.formula if not alt else prop.formula_alt
        formula_alt = prop.formula_alt if not alt else prop.formula
        if hint is None:
            result = self.model_check_formula(formula)
            result_alt = self.model_check_formula(formula_alt)
        else:
            result = self.model_check_formula_hint(formula, hint)
            result_alt = self.model_check_formula_hint(formula_alt, hint)

        state_quant = prop.state_quant
        compare_state = prop.compare_state

        value = result.at(self.initial_states[state_quant])
        # set the threshold
        threshold = result_alt.at(self.initial_states[compare_state])
        prop.set_threshold(threshold)
        Profiler.resume()
        return PropertyResult(prop, result, value)


class DTMC(MarkovChain):

    def check_constraints(self, properties, property_indices = None, short_evaluation = False):
        '''
        Check constraints.
        :param properties a list of all constraints
        :param property_indices a selection of property indices to investigate
        :param short_evaluation if set to True, then evaluation terminates as
          soon as a constraint is not satisfied
        '''

        # implicitly, check all constraints
        if property_indices is None:
            property_indices = [index for index,_ in enumerate(properties)]

        results = [None for prop in properties]
        grouped = Specification.or_group_indexes(property_indices)
        for group in grouped:
            if not group:
                continue
            unsat = True
            for index in group:
                prop = properties[index]
                result = self.model_check_property(prop)
                results[index] = result
                unsat = False if result.sat else unsat
            if short_evaluation and unsat:
                return ConstraintsResult(results)
        return ConstraintsResult(results)


class MDP(MarkovChain):

    # whether the secondary direction will be explored if primary is not enough
    compute_secondary_direction = False

    def __init__(self, model, quotient_container, quotient_state_map, quotient_choice_map, design_space):
        super().__init__(model, quotient_container, quotient_state_map, quotient_choice_map)

        self.design_space = design_space
        self.analysis_hints = None
        self.quotient_to_restricted_action_map = None

    def check_property(self, prop):

        # check primary direction
        primary = self.model_check_property(prop, alt = False)
        
        # no need to check secondary direction if primary direction yields UNSAT
        if not primary.sat:
            return MdpPropertyResult(prop, primary, None, False, None, None, None, None)

        # primary direction is SAT
        # check if the primary scheduler is consistent
        selection,choice_values,expected_visits,scores,consistent = self.quotient_container.scheduler_consistent(self, prop, primary.result)
        
        # regardless of whether it is consistent or not, we compute secondary direction to show that all SAT
        # compute secondary direction
        secondary = self.model_check_property(prop, alt = True)

        feasibility = True if secondary.sat else None
        return MdpPropertyResult(prop, primary, secondary, feasibility, selection, choice_values, expected_visits, scores)

    def check_constraints(self, properties, property_indices = None, short_evaluation = False):
        if property_indices is None:
            property_indices = [index for index,_ in enumerate(properties)]

        results = [None for prop in properties]
        grouped = Specification.or_group_indexes(property_indices)
        for group in grouped:
            if not group:
                continue
            unfeasible = True
            for index in group:
                prop = properties[index]
                result = self.check_property(prop)
                results[index] = result
                unfeasible = False if result.feasibility else unfeasible
            if short_evaluation and unfeasible:
                return MdpConstraintsResult(results)
        return MdpConstraintsResult(results)
