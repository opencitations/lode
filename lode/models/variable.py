from .resource import Resource

class Variable(Resource):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)