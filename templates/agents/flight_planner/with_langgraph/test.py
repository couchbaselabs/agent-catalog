import agentc
import json
import langchain_openai
import pytest
import ragas.dataset_schema
import ragas.embeddings
import ragas.llms
import ragas.metrics

from main import Graph


@pytest.fixture
def evaluator_llm() -> ragas.llms.LangchainLLMWrapper:
    chat_model = langchain_openai.chat_models.ChatOpenAI(model_name="gpt-4o", temperature=0)
    return ragas.llms.LangchainLLMWrapper(chat_model)


@pytest.fixture
def evaluator_embedding() -> ragas.embeddings.HuggingfaceEmbeddings:
    return ragas.embeddings.HuggingfaceEmbeddings(model_name=...)


@pytest.fixture
def catalog() -> agentc.Catalog:
    return agentc.Catalog()


def test_irrelevant_greetings(
    evaluator_llm: ragas.llms.LangchainLLMWrapper,
    evaluator_embedding: ragas.embeddings.HuggingfaceEmbeddings,
    catalog: agentc.Catalog,
    monkeypatch,
):
    suite_session = catalog.Span(name="irrelevant_greetings")
    with open("tests/irrelevant_greetings.jsonl") as fp:
        for i, line in enumerate(fp):

            def test_input():
                return json.loads(line)["input"]  # noqa: B023

            # The following will replace all uses of "input" with our test input.
            monkeypatch.setattr("builtins.input", test_input)
            with suite_session.Span(name=f"{i}") as test_session:
                graph = Graph(catalog=catalog, scope=test_session)
                result = graph.invoke(input=dict())

                # If our application set the endpoints or routes, this is a failing test.
                test_session["WereEndpointsSet"] = result["endpoints"]
                test_session["WasRouteSet"] = result["route"]

                # We will also record the semantic similarity of the result to our expected output below.
                expected_output = """
                    I'm sorry, I cannot help you with that.
                    Please provide me with a source and destination airport.
                """
                semantic_similarity_scorer = ragas.metrics.SemanticSimilarity(embeddings=evaluator_embedding)
                test_session["SemanticSimilarity"] = semantic_similarity_scorer.single_turn_score(
                    ragas.dataset_schema.SingleTurnSample(
                        response=result["messages"][-1].content, reference=expected_output
                    )
                )

                # Lastly, we'll use a critic to determine whether the agent response aligns with our expected output.
                asks_for_source_and_dest_scorer = ragas.metrics.AspectCritic(
                    name="ResponseAsksForSourceAndDestination",
                    definition="Does the response politely request the user to provide a source and destination "
                    "airport?",
                    llm=evaluator_llm,
                )
                test_session["ResponseAsksForSourceAndDestination"] = asks_for_source_and_dest_scorer.single_turn_score(
                    ragas.dataset_schema.SingleTurnSample(
                        response=result["messages"][-1].content,
                    )
                )
