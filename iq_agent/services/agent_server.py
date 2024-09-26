import dataclasses
import fastapi
import queue
import agentc
import threading
import uuid

# Note: this is a bit of hack, but some IDEs (like PyCharm) require the relative import when using FastAPI.
# try:
#     from simple_iq_agent import run_flow
# except ModuleNotFoundError:
#     from .simple_iq_agent import run_flow

try:
    from simple_iq_agent import run_flow
    from simple_iq_agent_using_base_agent import SimpleIQAgent
except ModuleNotFoundError:
    from .simple_iq_agent_using_base_agent import SimpleIQAgent
    from .simple_iq_agent import run_flow

agent_server = fastapi.FastAPI()
registry_lock = threading.Semaphore()
flow_registry = dict()
ig_agent = SimpleIQAgent()


@dataclasses.dataclass
class FlowHandle:
    flow_thread: threading.Thread
    to_user_queue: queue.Queue
    from_user_queue: queue.Queue


@agent_server.post("/feedback/{thread_id}")
def feedback(thread_id: str, content: str):
    auditor = agentc.Auditor(llm_name="gpt-4o")
    auditor.accept(
        role=agentc.auditor.Role.Feedback,
        content=content,
        session=thread_id,
    )
    return fastapi.Response(status_code=200)


@agent_server.post("/start")
def start_conversation():
    thread_id = uuid.uuid4().hex
    to_user_queue = queue.Queue()
    from_user_queue = queue.Queue()

    # Execute our flow (as a separate process)...
    flow_args = {"thread_id": thread_id, "to_user_queue": to_user_queue, "from_user_queue": from_user_queue}
    flow_thread = threading.Thread(target=run_flow, kwargs=flow_args)
    flow_thread.start()

    # ...register our flow...
    registry_lock.acquire()
    flow_registry[thread_id] = FlowHandle(
        flow_thread=flow_thread,
        to_user_queue=to_user_queue,
        from_user_queue=from_user_queue,
    )
    registry_lock.release()

    # ...and wait for the initial response to come back to our executor.
    initial_message = to_user_queue.get()
    to_user_queue.task_done()
    return {"thread_id": thread_id, "initial_message": initial_message}


@agent_server.post("/chat/{thread_id}")
def chat(thread_id: str, inp: str):
    registry_lock.acquire()
    flow_handle = flow_registry[thread_id]
    registry_lock.release()
    to_user_queue = flow_handle.to_user_queue
    from_user_queue = flow_handle.from_user_queue

    # Place the input message in the 'from_user_queue'...
    from_user_queue.join()
    from_user_queue.put(inp)

    # ...and wait for the output message to return.
    response = to_user_queue.get()
    to_user_queue.task_done()
    return {"response": response}
