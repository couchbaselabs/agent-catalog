import agentc
import json
import langchain_openai
import pathlib
import ragas.dataset_schema
import ragas.llms
import ragas.messages
import ragas.metrics
import unittest.mock


# Note: these tests should be run from the root of the project!
from main import Graph

# Our Agent Catalog objects (the same ones used for our application are used for tests as well).
# To denote that the following logs are associated with tests, we will name the Span after our test file.
catalog: agentc.Catalog = agentc.Catalog()
root_span: agentc.Span = catalog.Span(name=pathlib.Path(__file__).stem)

# For these tests, we will use OpenAI's GPT-4o model to evaluate the topic adherence of our agents.
evaluator_llm = ragas.llms.LangchainLLMWrapper(langchain_openai.chat_models.ChatOpenAI(name="gpt-4o", temperature=0))
scorer = ragas.metrics.TopicAdherenceScore(llm=evaluator_llm, mode="precision")


def eval_irrelevant_greetings():
    with (
        (pathlib.Path("evals") / "resources" / "irrelevant.jsonl").open() as fp,
        # To identify groups of evals (i.e., suites), we will use the name 'IrrelevantGreetings'.
        root_span.new("IrrelevantGreetings") as suite_span,
    ):
        for i, line in enumerate(fp):
            with (
                # To mock user input, we will use UnitTest's mock.patch to return the input from our JSONL file.
                unittest.mock.patch("builtins.input", lambda _: json.loads(line)["input"]),  # noqa: B023
                # To identify individual evals, we will use their line number + add their content as an annotation.
                suite_span.new(f"Test_{i}", test_input=line) as eval_span,
            ):
                graph: Graph = Graph(catalog=catalog, span=eval_span)
                for event in graph.stream(stream_mode="updates"):
                    if "front_desk_agent" in event:
                        # Run our app until the first response is given.
                        state = event["front_desk_agent"]
                        if len(state["messages"]) > 0 and any(m.type == "ai" for m in state["messages"]):
                            break

                # We are primarily concerned with whether the agent has correctly set "is_last_step" to True.
                eval_span["correctly_set_is_last_step"] = event["front_desk_agent"]["is_last_step"]


def eval_relevant_greetings():
    with (
        (pathlib.Path("evals") / "resources" / "relevant.jsonl").open() as fp,
        # To identify groups of evals (i.e., suites), we will use the name 'RelevantGreetings'.
        root_span.new("RelevantGreetings") as suite_span,
    ):
        for i, line in enumerate(fp):
            input_iter = iter(json.loads(line)["input"])
            with (
                # To mock user input, we will use UnitTest's mock.patch to return the input from our JSONL file.
                unittest.mock.patch("builtins.input", lambda _: next(input_iter)),  # noqa: B023
                # To identify individual evals, we will use their line number + add their content as an annotation.
                suite_span.new(f"Test_{i}", iterable=True, test_input=line) as eval_span,
            ):
                graph: Graph = Graph(catalog=catalog, span=eval_span)
                try:
                    graph.invoke()

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
                    sample = ragas.MultiTurnSample(user_input=ragas_input, reference_topics=["flights", "airports"])

                    # To record the results of this run, we will log the topic adherence score using our test_span.
                    score = scorer.multi_turn_score(sample)
                    eval_span["topic_adherence"] = score

                except StopIteration:
                    eval_span["correctly_set_is_last_step"] = False
