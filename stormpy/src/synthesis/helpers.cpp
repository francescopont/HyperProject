#include "synthesis.h"

#include "storm/modelchecker/CheckTask.h"
#include "storm/modelchecker/results/CheckResult.h"
#include "storm/environment/Environment.h"
#include "storm/api/verification.h"
#include "storm/modelchecker/hints/ExplicitModelCheckerHint.h"

#include "storm/storage/SparseMatrix.h"

#include "storm/utility/initialize.h"

template<typename ValueType>
std::shared_ptr<storm::modelchecker::CheckResult> modelCheckWithHint(
    std::shared_ptr<storm::models::sparse::Model<ValueType>> model,
    storm::modelchecker::CheckTask<storm::logic::Formula, ValueType> & task,
    storm::Environment const& env,
    std::vector<ValueType> hint_values
) {
    storm::modelchecker::ExplicitModelCheckerHint<ValueType> hint;
    hint.setComputeOnlyMaybeStates(false);
    hint.setNoEndComponentsInMaybeStates(false);
    hint.setResultHint(boost::make_optional(hint_values));
    task.setHint(std::make_shared<storm::modelchecker::ExplicitModelCheckerHint<ValueType>>(hint));
    return storm::api::verifyWithSparseEngine<ValueType>(env, model, task);
}

template<typename ValueType>
std::shared_ptr<storm::modelchecker::CheckResult> getExpectedNumberOfVisits(storm::Environment const& env, std::shared_ptr<storm::models::sparse::Model<ValueType>> const& model,
uint64_t initialState
) {
    return storm::api::computeExpectedVisitingTimesWithSparseEngineAndInitialState(env, model, initialState);
}


// Define python bindings
void define_helpers(py::module& m) {

    m.def("set_loglevel_off", []() { storm::utility::setLogLevel(l3pp::LogLevel::OFF); }, "set loglevel for storm to off");

    m.def("multiply_with_vector", [] (storm::storage::SparseMatrix<double> matrix,std::vector<double> vector) {
        std::vector<double> result(matrix.getRowCount());
        matrix.multiplyWithVector(vector, result);
        return result;
    }, py::arg("matrix"), py::arg("vector"));

    m.def("model_check_with_hint", &modelCheckWithHint<double>, "Perform model checking using the sparse engine", py::arg("model"), py::arg("task"), py::arg("environment"), py::arg("hint_values"));
    
    m.def("compute_expected_number_of_visits", &getExpectedNumberOfVisits<double>, py::arg("env"), py::arg("model"), py::arg("initialState"));

    m.def("construct_selection", [] ( storm::storage::BitVector default_actions, std::vector<uint_fast64_t> selected_actions) {
        auto bv = storm::storage::BitVector(default_actions);
        for(auto action: selected_actions)
            bv.set(action);
        return bv;
    }, py::arg("default_actions"), py::arg("selected_actions"));

}

