import stormpy

import math
import operator

from .spec import Specification

import logging

logger = logging.getLogger(__name__)


# Thread Scheduling formula
class TS_Unsat_Property:
    ''' Wrapper over a stormpy property. '''

    def __init__(self, prop, state_quant, compare_state, minimizing):
        self.property = prop
        rf = prop.raw_formula

        self.minimizing = minimizing
        self.op = operator.le if minimizing else operator.ge
        self.strict = False

        # the threshold is set at every model check query
        self.threshold = None

        # set optimality type
        self.formula = rf.clone()
        optimality_type = stormpy.OptimizationDirection.Minimize if minimizing else stormpy.OptimizationDirection.Maximize
        self.formula.set_optimality_type(optimality_type)

        # Construct alternative quantitative formula to use in AR.
        self.formula_alt = self.formula.clone()
        optimality_type_alt = stormpy.OptimizationDirection.Maximize if minimizing else stormpy.OptimizationDirection.Minimize
        self.formula_alt.set_optimality_type(optimality_type_alt)

        self.formula_str = rf

        # set the state quantifier (either 0 or 1)
        self.state_quant = state_quant
        self.compare_state = compare_state

    def double(self):
        state_quant = self.compare_state
        compare_state = self.state_quant
        minimizing = not self.minimizing
        return TS_Unsat_Property(self.property, state_quant, compare_state, minimizing)

    @property
    def reward(self):
        return False

    def __str__(self):
        other_state_quant = 0 if self.state_quant == 1 else 1
        return str(self.formula_str) + " " + str(self.state_quant) + " " + str(self.op) + " " + str(other_state_quant)

    @staticmethod
    def above_mc_precision(a, b):
        return abs(a - b) > Specification.mc_precision

    @staticmethod
    def above_float_precision(a, b):
        return abs(a - b) > Specification.float_precision

    def meets_op(self, a, b):
        return not TS_Unsat_Property.above_float_precision(a, b) or self.op(a, b)

    def satisfies_threshold(self, value):
        assert self.threshold is not None
        return self.meets_op(value, self.threshold)

    def set_threshold(self, threshold):
        self.threshold = threshold

    @classmethod
    def string_formulae(cls):
        return ["P=? [F \"l1\"]", "P=? [F \"l2\"]"]

    @classmethod
    def parse_specification(cls, prism):
        fs = TS_Unsat_Property.string_formulae()
        properties = []
        disjoint_indexes = []

        for f in fs:
            ps = stormpy.parse_properties_for_prism_program(f, prism)
            p = ps[0]
            p0_min = TS_Unsat_Property(p, 0, 1, minimizing=True)
            p1_min = TS_Unsat_Property(p, 1, 0, minimizing=True)

            properties.extend([p0_min, p1_min])

        # we have a conjunction of all properties
        for i, _ in enumerate(properties):
            disjoint_indexes.append([i])

        Specification.disjoint_indexes = disjoint_indexes
        return Specification(properties)

    @classmethod
    def parse_program(cls, sketch_path):
        return stormpy.parse_prism_program(sketch_path, prism_compat=True)