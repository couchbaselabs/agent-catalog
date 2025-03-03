import agentc
import controlflow
import typing


class Task(controlflow.Task):
    _accept_status: typing.Callable = None

    def __init__(self, node_name: str, scope: agentc.Span, **kwargs):
        super(Task, self).__init__(**kwargs)
        self._scope = scope
        self._node_name = node_name

    def run(self, *args, **kwargs):
        with self._scope.new(name=self._node_name):
            super(controlflow.Task, self).run(*args, **kwargs)


class TaskFactory:
    def __init__(
        self,
        span: agentc.Span,
        tools: list[typing.Any] = None,
        agent: controlflow.Agent = None,
    ):
        self.span: agentc.Span = span
        self.tools: list[typing.Any] = tools if tools is not None else list()
        self.agent: controlflow.Agent = agent

    def build(self, prompt: agentc.catalog.Prompt, **kwargs) -> controlflow.Task:
        tools = self.tools
        if prompt.tools:
            for t in prompt.tools:
                tools.append(controlflow.tools.Tool.from_function(t.func))

        # The remainder of this function is dependent on ControlFlow (the agent framework).
        kwargs_copy = kwargs.copy()
        if "tools" not in kwargs_copy:
            kwargs_copy["tools"] = tools
        if "objective" not in kwargs_copy:
            kwargs_copy["objective"] = prompt.content
        if "scope" not in kwargs_copy:
            kwargs_copy["scope"] = self.span
        if "agents" not in kwargs_copy and self.agent is not None:
            kwargs_copy["agents"] = [self.agent]
        if "result_type" not in kwargs_copy:
            kwargs_copy["result_type"] = prompt.output

        return Task(**kwargs_copy)

    def run(self, prompt: agentc.catalog.Prompt, **kwargs):
        return self.build(prompt, **kwargs).run()
