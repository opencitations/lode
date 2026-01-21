"""
Classe base per test RDF
"""
from reader.loader import Loader


class Test:
    """Classe madre per tutti i test RDF"""
    
    def __init__(self):
        self.results = []
    
    def test(self, name: str, source: str, should_work: bool = True):
        """
        Esegue un test di caricamento RDF
        
        Args:
            name: Nome del test
            source: URL o path del file
            should_work: Se ci aspettiamo che funzioni
        """
        print(f"\n🧪 Testing: {name}")
        print(f"   Source: {source}")
        
        try:
            loader = Loader(source)
            triples = len(loader.get_graph())
            
            if triples == 0:
                print(f"   ⚠️ WARNING - 0 triples loaded!")
                self.results.append({"test": name, "status": "WARNING", "triples": 0})
            elif should_work:
                print(f"   ✅ SUCCESS - {triples} triples loaded")
                self.results.append({"test": name, "status": "PASS", "triples": triples})
            else:
                print(f"   ❌ FAIL - Should have failed but loaded {triples} triples")
                self.results.append({"test": name, "status": "FAIL", "reason": "Unexpected success"})
                
        except Exception as e:
            if not should_work:
                print(f"   ✅ SUCCESS - Failed as expected: {str(e)[:50]}...")
                self.results.append({"test": name, "status": "PASS", "error": str(e)[:50]})
            else:
                print(f"   ❌ FAIL - {str(e)[:100]}")
                self.results.append({"test": name, "status": "FAIL", "reason": str(e)[:100]})
    
    def run_all_tests(self):
        """
        Metodo da implementare nelle sottoclassi
        """
        raise NotImplementedError("Implementa questo metodo nella sottoclasse")
    
    def print_summary(self):
        """Stampa il riepilogo dei risultati"""
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        warnings = sum(1 for r in self.results if r["status"] == "WARNING")
        
        for result in self.results:
            if result["status"] == "PASS":
                status_icon = "✅"
            elif result["status"] == "WARNING":
                status_icon = "⚠️"
            else:
                status_icon = "❌"
                
            print(f"{status_icon} {result['test']}: {result['status']}")
            
            if "triples" in result:
                print(f"   → {result['triples']} triples")
            if "reason" in result:
                print(f"   → {result['reason']}")
        
        print(f"\n{'='*60}")
        print(f"Total: {len(self.results)} | Passed: {passed} | Failed: {failed} | Warnings: {warnings}")
        print(f"{'='*60}\n")
        
        return failed == 0