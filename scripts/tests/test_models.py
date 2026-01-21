"""
Test per estrarre tutti gli individui di una classe specifica con i loro attributi.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reader.orchestrator import Reader
from reader.models import *


def format_value(value):
    """Formatta un valore per mostrare oggetto + identifier/value"""
    if isinstance(value, list):
        if not value:
            return "[]"
        
        # Controlla se è una lista di liste
        if all(isinstance(item, list) for item in value):
            # Lista di liste - formatta ricorsivamente ogni sottolista
            formatted = []
            for sublist in value:
                formatted.append(format_value(sublist))
            return f"[{', '.join(formatted)}]"
        else:
            # Lista di oggetti - mostra TUTTI gli elementi
            formatted = []
            for item in value:
                formatted.append(format_single_item(item))
            return f"[{', '.join(formatted)}]"
    elif isinstance(value, (int, float, bool)):
        return str(value)
    elif isinstance(value, str):
        return f'"{value}"'
    else:
        # Singolo oggetto
        return format_single_item(value)


def format_single_item(item):
    """Formatta un singolo item chiamando i suoi getter"""
    
    # PRIMA controlla se è un'istanza di Literal
    if item.__class__.__name__ == 'Literal':
        try:
            value = item.get_has_value() if hasattr(item, 'get_has_value') else getattr(item, 'has_value', None)
            lang = item.get_has_language() if hasattr(item, 'get_has_language') else getattr(item, 'has_language', None)
            datatype = item.get_has_type() if hasattr(item, 'get_has_type') else getattr(item, 'has_type', None)
            
            if value is None:
                return "Literal(empty)"
            
            if lang and datatype:
                return f'"{value}"@{lang}^^{datatype}'
            elif lang:
                return f'"{value}"@{lang}'
            elif datatype:
                return f'"{value}"^^{datatype}'
            return f'"{value}"'
        except Exception as e:
            return f"Literal(error: {e})"
    
    # POI controlla Resource (has_identifier, uri/bnods)
    if hasattr(item, 'get_has_identifier'):
        try:
            identifier = item.get_has_identifier()
            return f"{type(item).__name__}({identifier})"
        except:
            pass
    
    # Altrimenti mostra solo il tipo
    return f"{type(item).__name__}"


def print_instance_attributes(instance, instance_number=None):
    """Stampa tutti gli attributi di un'istanza"""
    
    header = f"INSTANCE #{instance_number}" if instance_number else "INSTANCE"
    print(f"\n{'-' * 70}")
    print(header)
    print(f"{'-' * 70}")
    print(f"Type: {type(instance).__name__}")
    print(f"URI: {instance.get_has_identifier()}")
    print(f"{'-' * 70}\n")
    
    # Trova TUTTI i getter con dir()
    getters = [m for m in dir(instance) if m.startswith('get_') and callable(getattr(instance, m))]
    
    attribute_count = 0
    for getter_name in sorted(getters):
        try:
            getter_method = getattr(instance, getter_name)
            value = getter_method()
            
            # Salta valori vuoti
            if value is None or value == [] or value == '':
                continue
            
            attribute_count += 1
            field_name = getter_name.replace('get_', '')
            formatted_value = format_value(value)
            print(f"  • {field_name}: {formatted_value}")
            
        except Exception as e:
            pass  # Ignora errori nei getter
    
    print(f"\n{'-' * 70}")
    print(f"Total attributes: {attribute_count}")
    print(f"{'-' * 70}")


def extract_instances_by_class(reader: Reader, python_class: type):
    """
    Estrae tutte le istanze di una classe specifica e stampa i loro attributi.
    
    Args:
        reader: Istanza di Reader già caricata
        python_class: Classe Python da cercare (es. Concept, Property, Restriction, ecc.)
    """
    print(f"\n{'=' * 70}")
    print(f"EXTRACTING ALL INSTANCES OF CLASS: {python_class.__name__}")
    print(f"{'=' * 70}")
    
    # Ottieni tutte le istanze raggruppate per classe
    all_instances = reader.get_instances()
    
    # Filtra solo le istanze della classe richiesta
    class_name = python_class.__name__
    instances = all_instances.get(class_name, [])
    
    if not instances:
        print(f"\n No instances found for class {class_name}\n")
        return
    
    print(f"\nFound {len(instances)} instance(s)\n")
    
    # Stampa ogni istanza con i suoi attributi
    for i, instance in enumerate(instances, 1):
        print_instance_attributes(instance, instance_number=i)


def run_test_suite():
    """Esegue la suite completa di test"""
    
    # ========== TEST 1: Pizza Ontology - Concepts ==========
    # print("\n# TEST 1: PIZZA ONTOLOGY - Extract all Concepts\n")
    
    # pizza_reader = Reader()
    # pizza_reader.clear_cache()
    # pizza_reader.load_instances(
    #     "https://protege.stanford.edu/ontologies/pizza/pizza.owl", 
    #     read_as='OWL'
    # )
    
    # extract_instances_by_class(pizza_reader, Concept)
    
    # # ========== TEST 2: Pizza Ontology - Relations ==========
    # print("\n# TEST 2: PIZZA ONTOLOGY - Extract all Relations\n")
    
    # extract_instances_by_class(pizza_reader, Relation)
    
    # # ========== TEST 3: Pizza Ontology - Restrictions ==========
    # print("\n# TEST 3: PIZZA ONTOLOGY - Extract all Restrictions\n")
    
    # extract_instances_by_class(pizza_reader, Restriction)
    
    # # ========== TEST 4: Pizza Ontology - Quantifiers ==========
    # print("\n# TEST 4: PIZZA ONTOLOGY - Extract all Quantifiers\n")
    
    # extract_instances_by_class(pizza_reader, Quantifier)

    # # ========== TEST 5: Pizza Ontology - Values ==========
    # print("\n# TEST 4: PIZZA ONTOLOGY - Extract all Values\n")
    
    # extract_instances_by_class(pizza_reader, Value)
    
    # # ========== TEST 5: Pizza Ontology - OneOf ==========
    # print("\n# TEST 4: PIZZA ONTOLOGY - Extract all OneOf\n")
    
    # extract_instances_by_class(pizza_reader, OneOf)

    # # ========== TEST 5: Pizza Ontology - TruthFunction ==========
    # print("\n# TEST 4: PIZZA ONTOLOGY - Extract all TruthFunction\n")
    
    # extract_instances_by_class(pizza_reader, TruthFunction)

    # # ========== TEST 5: Pizza Ontology - Restriction ==========
    # print("\n# TEST 4: PIZZA ONTOLOGY - Extract all Restrictions\n")
    
    # extract_instances_by_class(pizza_reader, Restriction)

    #     # ========== TEST 11: Pizza Ontology - Individuals ==========
    # print("\n# TEST 11: Pizza ONTOLOGY - Extract all Individuals\n")
    
    # extract_instances_by_class(pizza_reader, Individual)

    # # ========== TEST 11: Pizza Ontology - Individuals ==========
    # print("\n# TEST 12: Pizza ONTOLOGY - Extract all Statements\n")
    
    # extract_instances_by_class(pizza_reader, Statement)

    # # ========== TEST 11: Pizza Ontology - Property ==========
    # print("\n# TEST 12: Pizza ONTOLOGY - Extract all Properties\n")
    
    # extract_instances_by_class(pizza_reader, Property)

    # # ========== TEST 11: Pizza Ontology - Property ==========
    # print("\n# TEST 13: Pizza ONTOLOGY - Extract all Cardinalities\n")
    
    # extract_instances_by_class(pizza_reader, Cardinality)

    # ========== TEST 6: ICON Ontology - Quantifiers ==========
    print("\n# TEST 5: ICON ONTOLOGY - Extract all Quantifiers\n")

    # foaf ontology: https://gist.githubusercontent.com/baskaufs/fefa1bfbff14a9efc174/raw/389e4b003ef5cbd6901dd8ab8a692b501bc9370e/foaf.ttl
    # rdf_vocab: https://raw.githubusercontent.com/ColinMaudry/dita-rdf/master/dita.ttl 



    icon_reader = Reader()
    icon_reader.clear_cache()
    icon_reader.load_instances(
        "https://gist.githubusercontent.com/baskaufs/fefa1bfbff14a9efc174/raw/389e4b003ef5cbd6901dd8ab8a692b501bc9370e/foaf.ttl", 
        read_as='RDF'
    )

    extract_instances_by_class(icon_reader, Property)
    extract_instances_by_class(icon_reader, Container)
    extract_instances_by_class(icon_reader, Statement)
    extract_instances_by_class(icon_reader, Relation)


    # ========== TEST 7: ICON Ontology - Relations ==========
    # print("\n# TEST 6: ICON ONTOLOGY - Extract all Relations\n")
    
    # extract_instances_by_class(icon_reader, Relation)
    
    
    # # extract_instances_by_class(icon_reader, Quantifier)
    
    # # ========== TEST 7: ICON Ontology - Cardinality ==========
    # print("\n# TEST 6: ICON ONTOLOGY - Extract all Cardinality Restrictions\n")
    
    # extract_instances_by_class(icon_reader, Cardinality)

    # # ========== TEST 7: ICON Ontology - Concepts ==========
    # print("\n# TEST 6: ICON ONTOLOGY - Extract Concepts \n")
    
    # extract_instances_by_class(icon_reader, Concept)

    # # ========== TEST 7: ICON Ontology - TruthFunctions ==========
    # print("\n# TEST 6: ICON ONTOLOGY - TruthFunctions \n")
    
    # extract_instances_by_class(icon_reader, TruthFunction)

    # # ========== TEST 7: ICON Ontology - TruthFunctions ==========
    # print("\n# TEST 6: ICON ONTOLOGY - Statement \n")
    
    # extract_instances_by_class(icon_reader, Statement)

    # # ========== TEST 7: ICON Ontology - TruthFunctions ==========
    # print("\n# TEST 6: ICON ONTOLOGY - Attribute \n")
    
    # extract_instances_by_class(icon_reader, Attribute)

    # # ========== TEST 7: ICON Ontology - Restriction ==========
    # print("\n# TEST 6: ICON ONTOLOGY - Attribute \n")
    
    # extract_instances_by_class(icon_reader, Restriction)

    # # ========== TEST 7: ICON Ontology - Individual ==========
    # print("\n# TEST 6: ICON ONTOLOGY - Individual \n")
    
    # extract_instances_by_class(icon_reader, Individual)
    
    # ========== TEST 8: SKOS - Concepts ==========
    # print("\n# TEST 7: SKOS VOCABULARY - Extract all Concepts\n")

    
    
    # skos_reader = Reader()
    # skos_reader.clear_cache()
    # skos_reader.load_instances(
    #     "https://raw.githubusercontent.com/br0ast/ICON/main/Ontology/current/icon.rdf", 
    #     read_as='SKOS'
    # )
    
    # extract_instances_by_class(skos_reader, Restriction)
    # extract_instances_by_class(skos_reader, Concept)
    # extract_instances_by_class(skos_reader, Property)
    # extract_instances_by_class(skos_reader, Relation)
    # extract_instances_by_class(skos_reader, Collection)
    # extract_instances_by_class(skos_reader, Model)
    # extract_instances_by_class(skos_reader, Resource)
    
    # # ========== TEST 9: CiTO - Properties ==========
    # print("\n# TEST 8: CiTO ONTOLOGY - Extract all Properties\n")
    
    # cito_reader = Reader()
    # cito_reader.clear_cache()
    # cito_reader.load_instances("http://purl.org/spar/cito/", read_as='OWL')
    
    # extract_instances_by_class(cito_reader, Property)

    # # ========== TEST 10: ICON Ontology - Individuals ==========
    # print("\n# TEST 10: ICON ONTOLOGY - Extract all Individuals\n")
    
    # extract_instances_by_class(icon_reader, Individual)


if __name__ == "__main__":
    run_test_suite()