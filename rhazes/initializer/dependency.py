import inspect

from rhazes.collections.stack import UniqueStack


class DependencyNode:
    def __init__(self, cls, dependency_position, args):
        self.cls = cls
        self.dependencies = []

    def add_dependency(self, dependency: "DependencyNode"):
        self.dependencies.append(dependency)


class DependencyProcessor:

    def __init__(self, all_classes: list):
        self.all_classes = all_classes
        self.objects = {}
        self.listeners = {}
        self.node_registry = {}
        self.node_metadata_registry = {}

    def register_node(self, cls) -> DependencyNode:
        if cls in self.node_registry:
            return self.node_registry[cls]
        node = DependencyNode(cls)
        self.node_registry[cls] = node
        return node

    def register_metadata(self, cls) -> tuple:
        """

        :param cls: class to get arguments of
        :return: tuple:
            - dependencies: list of dependency classes
            - dependency_position: dictionary of dependency class positions in arguments
            - args: list of prefilled arguments to be used as *args for constructing
        """
        args = []
        dependencies = []
        dependency_position = {}
        signature = inspect.signature(cls.__init__)
        i = 0
        for k, v in signature.parameters.items():
            if k == "self":
                continue
            if v.annotation in self.all_classes:
                dependencies.append(v.annotation)
                args[i] = None
                dependency_position[v.annotation] = i
            elif v.default == v.empty:
                raise Exception()  # Todo: depends on a object that is not in service classes
            else:
                args[i] = v.default
            i += 1
        self.node_metadata_registry[cls] = {
            "dependencies": dependencies,
            "dependency_position": dependency_position,
            "args": args,
        }

    def make_object(self, cls, dependencies: list, dependency_position: dict, args: list):
        for dep in dependencies:
            if dep not in self.objects:
                self.add_listener(dep, lambda x: self.make_object(cls, dependencies, dependency_position, args))
                return
        for dep in dependencies:
            args[dependency_position[dep]] = self.objects[dep]
        obj = cls(*args)
        self.objects[cls] = obj

    def process(self):
        to_process = []

        # Building Graph
        for cls in self.all_classes:
            dependencies, dependency_position, args = self.register_metadata(cls)
            node = self.register_node(cls)
            for dependency in dependencies:
                node.add_dependency(self.register_node(dependency))
            to_process.append(node)

        # Processing each node
        for node in to_process:
            self._process(node, UniqueStack())

        return self.objects

    def _process(self, node, stack):
        """
        Depth first traversal on nodes.
            Base case: node is already built, so we ignore building again
            Using "post-order" BFS to use a UniqueStack in order to detect cycles

        Accepts any node and if its already processed ignores it.
        The reason is that we aren't sure we have a single dependency tree or graph or multiple ones
        That's why this method is called for all service classes

        :param node: a node to start processing from
        :param stack: instance of UniqueStack for dependency cycle detection
        :return:
        """
        if node.cls in self.objects:
            return
        stack.append(node)
        for child in node.dependencies:
            self._process(child, stack)
        self.build(node)
        stack.pop()

    def build(self, node: DependencyNode):
        metadata = self.node_metadata_registry[node.cls]
        for dep in metadata["dependencies"]:
            metadata["args"][metadata["dependency_position"][dep]] = self.objects[dep]
        obj = node.cls(*metadata["args"])
        self.objects[node.cls] = obj
