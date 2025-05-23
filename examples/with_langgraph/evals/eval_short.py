import agentc
import json
import langchain_openai
import pathlib
import ragas.dataset_schema
import ragas.llms
import ragas.messages
import ragas.metrics
import unittest.mock


# Note: these evals should be run from the root of the project!
from graph import FlightPlanner

# Our Agent Catalog objects (the same ones used for our application are used for tests as well).
# To denote that the following logs are associated with tests, we will name the Span after our test file.
catalog: agentc.Catalog = agentc.Catalog()
root_span: agentc.Span = catalog.Span(name=pathlib.Path(__file__).stem)

# For these tests, we will GPT-4o to evaluate the similarity of our agent's response and our reference.
evaluator_llm = ragas.llms.LangchainLLMWrapper(langchain_openai.chat_models.ChatOpenAI(name="gpt-4o", temperature=0))
scorer = ragas.metrics.SimpleCriteriaScore(
    name="coarse_grained_score", llm=evaluator_llm, definition="Score 0 to 5 by similarity."
)


def eval_bad_intro():
    with (
        (pathlib.Path("evals") / "resources" / "bad-intro.jsonl").open() as fp,
        # To identify groups of evals (i.e., suites), we will use the name 'IrrelevantGreetings'.
        root_span.new("IrrelevantGreetings") as suite_span,
    ):
        for i, line in enumerate(fp):
            with (
                # To mock user input, we will use UnitTest's mock.patch to return the input from our JSONL file.
                unittest.mock.patch("builtins.input", lambda _: json.loads(line)["input"]),  # noqa: B023
                # We will also swallow any output that the FrontDeskAgent may produce.
                unittest.mock.patch("builtins.print", lambda *args, **kwargs: None),  # noqa: B023
                # To identify individual evals, we will use their line number + add their content as an annotation.
                suite_span.new(f"Eval_{i}", test_input=line) as eval_span,
            ):
                graph: FlightPlanner = FlightPlanner(catalog=catalog, span=eval_span)
                state = FlightPlanner.build_starting_state()
                for event in graph.stream(input=state, stream_mode="updates"):
                    if "front_desk_agent" in event:
                        # Run our app until the first response is given.
                        state = event["front_desk_agent"]
                        if len(state["messages"]) > 0 and any(m.type == "ai" for m in state["messages"]):
                            break

                # We are primarily concerned with whether the agent has correctly set "is_last_step" to True.
                eval_span["correctly_set_is_last_step"] = event["front_desk_agent"]["is_last_step"]


def eval_short_threads():
    with (
        (pathlib.Path("evals") / "resources" / "short-thread.jsonl").open() as fp,
        # To identify groups of evals (i.e., suites), we will use the name 'ShortThreads'.
        root_span.new("ShortThreads") as suite_span,
    ):
        for i, line in enumerate(fp):
            input_iter = iter(json.loads(line)["input"])
            reference = json.loads(line)["reference"]
            with (
                # To mock user input, we will use UnitTest's mock.patch to return the input from our JSONL file.
                unittest.mock.patch("builtins.input", lambda _: next(input_iter)),  # noqa: B023
                # We will also swallow any output that the FrontDeskAgent may produce.
                unittest.mock.patch("builtins.print", lambda *args, **kwargs: None),  # noqa: B023
                # To identify individual evals, we will use their line number + add their content as an annotation.
                suite_span.new(f"Eval_{i}", iterable=True, test_input=line) as eval_span,
            ):
                graph: FlightPlanner = FlightPlanner(catalog=catalog, span=eval_span)
                try:
                    state = FlightPlanner.build_starting_state()
                    graph.invoke(input=state)

                    # If we have reached here, then our agent system has correctly processed our input!
                    eval_span["correctly_set_is_last_step"] = True

                    # Now, convert the content we logged into Ragas-friendly list.
                    ragas_input: list[ragas.messages.Message] = list()
                    for log in eval_span:
                        content = log.content
                        match content.kind:
                            case agentc.span.ContentKind.Assistant:
                                assistant_message: agentc.span.AssistantContent = content
                                ragas_input.append(ragas.messages.AIMessage(content=assistant_message.value))
                            case agentc.span.ContentKind.User:
                                user_message: agentc.span.UserContent = content
                                ragas_input.append(ragas.messages.HumanMessage(content=user_message.value))
                            case _:
                                pass
                    sample = ragas.MultiTurnSample(user_input=ragas_input, reference=reference)

                    # To record the results of this run, we will log the goal accuracy score using our eval_span.
                    score = scorer.multi_turn_score(sample)
                    eval_span["goal_accuracy"] = {
                        "score": score,
                        "reference": reference,
                    }

                except (StopIteration, RuntimeError):
                    eval_span["correctly_set_is_last_step"] = False
                    eval_span["goal_accuracy"] = {"score": 0, "reference": reference}


if __name__ == "__main__":
    eval_bad_intro()
    eval_short_threads()
