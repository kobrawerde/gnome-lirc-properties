from logilab import astng

from pylint.interfaces import IASTNGChecker
from pylint.checkers import BaseChecker

class MyChecker(BaseChecker):
    __implements__ = IASTNGChecker

    name = 'custom'
    msgs, options = {}, ()
    priority = -1 # execute before others

    def visit_function(self, node):
        widget_list_nodes = (
            '__lookup_widgets' == node.name and
            node.frame().locals.get('widget_list') or [])

        if widget_list_nodes:
            self.__register_widget_attributes(node.parent.frame(),
                                              widget_list_nodes)

    def __register_widget_attributes(self, frame, nodes):
        for local_node in nodes:
            if isinstance(local_node, astng.AssName):
                for expr in local_node.parent.expr.nodes:
                    if isinstance(expr, astng.Const):
                        value = astng.Name('widget:%s' % expr.value)
                        frame.set_local('__%s' % expr.value, value)

def register(linter):
    '''auto register this checker'''
    linter.register_checker(MyChecker(linter))
