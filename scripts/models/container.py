from .resource import Resource

class Container(Resource):
    """RDF Container (Bag, Seq, Alt, List)"""
    
    def __init__(self):
        super().__init__()
        self.members = []
    
    def set_has_member(self, member):
        """Aggiunge un singolo membro"""
        if member not in self._members:
            self.members.append(member)
    
    def set_has_members(self, members: list):
        """Imposta tutti i membri in una volta"""
        self._members = members.copy()
    
    def get_has_members(self):
        """Ritorna la lista dei membri"""
        return self.members.copy()
