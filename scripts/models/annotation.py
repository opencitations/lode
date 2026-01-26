from .property import Property

class Annotation(Property):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)