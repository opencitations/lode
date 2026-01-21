"""
HTML Generator per ontologie RDF - VERSIONE CON STATEMENTS NESTED NEI SOGGETTI
Genera pagine HTML navigabili con:
- Statements raggruppati per entità soggetto
- Statement instances mostrati dentro la card del soggetto
- CSS e JS esterni
- Layout modulare e pulito
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reader import Reader
from models import *
from typing import Dict, List, Any, Set, Tuple
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
import html
from collections import defaultdict

class OntologyHTMLGenerator:
    """Genera HTML da istanze di ontologie con statements nested nei soggetti"""
    
    def __init__(self, reader: Reader):
        self.reader = reader
        self.instances = reader.get_instances()
        self.triples_map = reader.get_all_triples_map()
        
        # Raggruppa statements RDF per soggetto URI
        self.statements_by_subject = self._group_statements_by_subject()
        
        # Raggruppa Statement instances per soggetto
        self.statement_instances_by_subject = self._group_statement_instances()
        
    def _group_statements_by_subject(self) -> Dict[str, Set[Tuple]]:
        """
        Raggruppa tutti gli statements RDF per URI del soggetto
        Returns: {subject_uri: {(subj, pred, obj), ...}}
        """
        statements_map = defaultdict(set)
        
        for instance, triples in self.triples_map.items():
            for subj, pred, obj in triples:
                # Usa l'URI del soggetto come chiave
                subj_uri = str(subj)
                statements_map[subj_uri].add((subj, pred, obj))
        
        return dict(statements_map)
    
    def _group_statement_instances(self) -> Dict[str, List[Any]]:
        """
        Raggruppa le istanze di Statement per il loro soggetto
        Returns: {subject_uri: [statement_instance1, statement_instance2, ...]}
        """
        statements_by_subj = defaultdict(list)
        
        # Cerca tutte le istanze che hanno il metodo get_has_subject
        for class_name, instances_list in self.instances.items():
            for instance in instances_list:
                if hasattr(instance, 'get_has_subject'):
                    try:
                        subject = instance.get_has_subject()
                        if subject and hasattr(subject, 'get_has_identifier'):
                            subject_uri = subject.get_has_identifier()
                            statements_by_subj[subject_uri].append(instance)
                    except:
                        pass
        
        return dict(statements_by_subj)
        
    def _escape(self, text: str) -> str:
        """Escape HTML"""
        return html.escape(str(text))
    
    def _format_value(self, value: Any) -> str:
        """Formatta un valore in HTML"""
        if value is None or value == [] or value == '':
            return '<span class="empty">—</span>'
        
        if isinstance(value, list):
            if not value:
                return '<span class="empty">[]</span>'
            
            items_html = []
            for item in value:
                items_html.append(self._format_single_item(item))
            
            # Lista inline per valori corti
            if len(items_html) <= 3 and all(len(str(i)) < 50 for i in items_html):
                return ', '.join(items_html)
            
            return '<ul class="value-list">' + ''.join(f'<li>{i}</li>' for i in items_html) + '</ul>'
        
        return self._format_single_item(value)
    
    def _get_entity_category_info(self, instance: Any) -> tuple:
        """
        Determina categoria e colore per un'entità
        Returns: (category_name, category_initial, color_hex)
        """
        class_name = type(instance).__name__
        
        # Mappa classi -> categorie con colori distintivi
        category_map = {
            # Core RDF
            'Statement': ('Statement', 'ST', '#95a5a6'),  # Grigio
            'Property': ('Property', 'P', '#3498db'),  # Blu
            'Resource': ('Resource', 'R', '#34495e'),  # Grigio scuro
            'Literal': ('Literal', 'L', '#bdc3c7'),  # Grigio chiaro
            'Datatype': ('Datatype', 'DT', '#7f8c8d'),  # Grigio medio
            'Container': ('Container', 'CN', '#2c3e50'),  # Blu scuro
            
            # SKOS
            'Concept': ('Concept', 'C', '#e74c3c'),  # Rosso
            'Collection': ('Collection', 'CL', '#e84393'),  # Rosa
            
            # RDFS/OWL Extended
            'Relation': ('Relation', 'RL', '#9b59b6'),  # Viola
            'Attribute': ('Attribute', 'A', '#f39c12'),  # Oro
            'Individual': ('Individual', 'I', '#1abc9c'),  # Turchese
            'Model': ('Model', 'M', '#27ae60'),  # Verde
            'Annotation': ('Annotation', 'AN', '#16a085'),  # Verde acqua
            
            # OWL Logic
            'TruthFunction': ('Truth Function', 'TF', '#8e44ad'),  # Viola scuro
            'Value': ('Value', 'V', '#d35400'),  # Arancione scuro
            'OneOf': ('OneOf', 'OF', '#c0392b'),  # Rosso scuro
            'Quantifier': ('Quantifier', 'Q', '#2980b9'),  # Blu scuro
            'Cardinality': ('Cardinality', 'CR', '#e67e22'),  # Arancione
            'PropertyConceptRestriction': ('Property Restriction', 'PR', '#6c5ce7'),  # Indaco
            'Restriction': ('Restriction', 'RS', '#a29bfe'),  # Viola chiaro
        }
        
        return category_map.get(class_name, ('Entity', 'E', '#95a5a6'))

    def _format_single_item(self, item: Any) -> str:
        """Formatta un singolo item con badge categoria colorato"""
        
        # Literal
        if item.__class__.__name__ == 'Literal':
            try:
                value = item.get_has_value() if hasattr(item, 'get_has_value') else None
                lang = item.get_has_language() if hasattr(item, 'get_has_language') else None
                
                datatype_obj = item.get_has_datatype() if hasattr(item, 'get_has_datatype') else None
                datatype = None
                if datatype_obj:
                    if hasattr(datatype_obj, 'get_has_identifier'):
                        datatype_full = datatype_obj.get_has_identifier()
                        datatype = datatype_full.split('#')[-1].split('/')[-1] if datatype_full else None
                
                if value is None:
                    return '<span class="literal empty">—</span>'
                
                escaped_value = self._escape(value)
                
                # ✨ BADGE CATEGORIA PER LITERAL
                _, initial, color = self._get_entity_category_info(item)
                badge = f'<span class="entity-badge" style="background-color: {color}; color: white;" title="Literal">{initial}</span>'
                
                badges = [badge]
                if lang:
                    badges.append(f'<span class="badge lang">{lang}</span>')
                if datatype:
                    badges.append(f'<span class="badge type">{datatype}</span>')
                
                badge_html = ''.join(badges)
                return f'<span class="literal">"{escaped_value}" {badge_html}</span>'
            except Exception as e:
                return f'<span class="literal error">Error: {e}</span>'
        
        # Tipi primitivi Python (nessun badge)
        if isinstance(item, (int, float)):
            value_str = str(item)
            type_name = type(item).__name__
            return f'<span class="primitive">{value_str}<span class="badge type">{type_name}</span></span>'
        
        if isinstance(item, bool):
            if item is False:
                return ''
            value_str = str(item)
            type_name = type(item).__name__
            return f'<span class="primitive">{value_str}<span class="badge type">{type_name}</span></span>'

        if isinstance(item, str):
            escaped_value = self._escape(item)
            return f'<span class="primitive">"{escaped_value}"<span class="badge type">str</span></span>'
        
        if isinstance(item, list):
            if not item:
                return '<div class="python-list empty-list"><span class="list-label">list[0]</span><div class="empty-list-msg">Empty list</div></div>'
            
            items_html = []
            for subitem in item:
                items_html.append(self._format_single_item(subitem))
            
            list_content = ''.join(f'<li>{i}</li>' for i in items_html)
            return f'<div class="python-list"><span class="list-label"></span><ul class="list-items">{list_content}</ul></div>'

        # Resource con identifier E BADGE CATEGORIA
        if hasattr(item, 'get_has_identifier'):
            try:
                identifier = item.get_has_identifier()
                class_name = type(item).__name__
                link_id = identifier.replace(':', '_').replace('/', '_').replace('#', '_')
                
                display_name = identifier.split('/')[-1].split('#')[-1] if identifier else class_name
                
                # ✨ OTTIENI CATEGORIA E COLORE
                category_name, category_initial, color = self._get_entity_category_info(item)
                
                # ✨ BADGE COLORATO
                badge_html = f'<span class="entity-badge" style="background-color: {color}; color: white;" title="{category_name}">{category_initial}</span>'
                
                return f'<a href="#{link_id}" class="resource-link" title="{self._escape(identifier)}">{badge_html}{self._escape(display_name)}</a>'
            except:
                pass
        
        return f'<span class="resource">{self._escape(type(item).__name__)}</span>'

    def _format_rdf_node(self, node) -> str:
        """Formatta nodo RDF per visualizzazione"""
        if isinstance(node, URIRef):
            uri_str = str(node)
            return f'&lt;{self._escape(uri_str)}&gt;'
        
        elif isinstance(node, BNode):
            return f'_:{node}'
        
        elif isinstance(node, RDFlibLiteral):
            value = str(node)
            if len(value) > 80:
                value = value[:77] + '...'
            
            value = self._escape(value)
            
            lang = f'@{node.language}' if node.language else ''
            
            dtype = ''
            if node.datatype:
                dtype_str = str(node.datatype)
                if dtype_str.startswith('http://www.w3.org/2001/XMLSchema#'):
                    dtype_str = 'xsd:' + dtype_str.split('#')[1]
                dtype = f'^^{dtype_str}'
            
            return f'"{value}"{lang}{dtype}'
        
        return self._escape(str(node))

    def _generate_fallback_css(self) -> str:
        """CSS minimo di fallback"""
        return """
        body { font-family: sans-serif; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 30px; }
        .instance-card { border: 1px solid #ddd; margin: 10px 0; padding: 15px; }
        .accordion-toggle { cursor: pointer; background: #eee; border: none; padding: 10px; width: 100%; text-align: left; }
        .accordion-content { max-height: 0; overflow: hidden; transition: max-height 0.3s; }
        .accordion-content.open { max-height: 500px; overflow-y: auto; }
        .statement-box { background: #f9f9f9; border-left: 3px solid #4CAF50; padding: 10px; margin: 10px 0; }
        .statement-header { font-weight: bold; margin-bottom: 5px; }
        """
    
    def _generate_fallback_js(self) -> str:
        """JavaScript minimo di fallback"""
        return """
        function toggleAccordion(id) {
            const content = document.getElementById(id);
            const button = content.previousElementSibling;
            if (content.classList.contains('open')) {
                content.classList.remove('open');
                button.classList.remove('active');
            } else {
                content.classList.add('open');
                button.classList.add('active');
            }
        }
        """

    def _generate_statement_html(self, statement: Any, statement_index: int, parent_id: str) -> str:
        """Genera HTML per un Statement instance"""
        
        html_parts = []
        statement_id = f"{parent_id}-stmt-{statement_index}"
        
        html_parts.append(f'<div class="statement-box" id="{statement_id}">')
        
        # Header dello statement
        class_name = type(statement).__name__
        html_parts.append(f'  <div class="statement-header">')
        html_parts.append(f'    <span class="statement-icon">📝</span>')
        html_parts.append(f'    <span class="statement-label">Statement #{statement_index}</span>')
        html_parts.append(f'    <span class="statement-type">{self._escape(class_name)}</span>')
        html_parts.append(f'  </div>')
        
        # Proprietà dello statement
        html_parts.append(f'  <div class="statement-props">')
        
        getters = [m for m in dir(statement) if m.startswith('get_') and callable(getattr(statement, m))]
        
        for getter_name in sorted(getters):
            # Skippa il soggetto (già mostrato nella card principale)
            if getter_name == 'get_has_subject':
                continue
            
            try:
                getter_method = getattr(statement, getter_name)
                value = getter_method()
                
                if value is None or value == [] or value == '':
                    continue
                
                if isinstance(value, bool) and value is False:
                    continue
                
                field_name = getter_name.replace('get_', '').replace('has_', '').replace('_', ' ')
                formatted_value = self._format_value(value)
                
                html_parts.append(f'    <div class="statement-prop">')
                html_parts.append(f'      <span class="prop-name">{self._escape(field_name)}:</span>')
                html_parts.append(f'      <span class="prop-value">{formatted_value}</span>')
                html_parts.append(f'    </div>')
            except:
                pass
        
        html_parts.append(f'  </div>')
        
        # Triple RDF associate allo statement
        statement_identifier = statement.get_has_identifier() if hasattr(statement, 'get_has_identifier') else None
        if statement_identifier:
            statement_triples = self.statements_by_subject.get(statement_identifier, set())
            
            if statement_triples:
                accordion_id = f"stmt-triples-{statement_id}"
                triple_count = len(statement_triples)
                
                html_parts.append(f'  <div class="statement-triples-accordion">')
                html_parts.append(f'    <button class="accordion-toggle small" onclick="toggleAccordion(\'{accordion_id}\')">')
                html_parts.append(f'      <span class="toggle-icon">▶</span>')
                html_parts.append(f'      <span class="toggle-text">RDF Triples ({triple_count})</span>')
                html_parts.append(f'    </button>')
                html_parts.append(f'    <div class="accordion-content" id="{accordion_id}">')
                
                for subj, pred, obj in sorted(statement_triples, key=lambda x: str(x[1])):
                    subj_str = self._format_rdf_node(subj)
                    pred_str = self._format_rdf_node(pred)
                    obj_str = self._format_rdf_node(obj)
                    
                    html_parts.append(f'      <div class="triple-line">')
                    html_parts.append(f'        <span class="triple-s">{subj_str}</span>')
                    html_parts.append(f'        <span class="triple-p">{pred_str}</span>')
                    html_parts.append(f'        <span class="triple-o">{obj_str}</span>')
                    html_parts.append(f'        <span class="triple-dot">.</span>')
                    html_parts.append(f'      </div>')
                
                html_parts.append(f'    </div>')
                html_parts.append(f'  </div>')
        
        html_parts.append(f'</div>')
        
        return '\n'.join(html_parts)

    def _generate_instance_html(self, instance: Any, index: int) -> str:
        """Genera HTML per una singola istanza CON COLORE COORDINATO"""
        
        class_name = type(instance).__name__
        identifier = instance.get_has_identifier() if hasattr(instance, 'get_has_identifier') else None
        
        if identifier is None:
            identifier = f"_blank_node_{id(instance)}"
            link_id = f"blank_{index}_{id(instance)}"
        else:
            link_id = identifier.replace(':', '_').replace('/', '_').replace('#', '_')
        
        display_name = identifier.split('/')[-1].split('#')[-1] if identifier and identifier.startswith('http') else identifier
        
        # ✨ OTTIENI COLORE PER QUESTA CATEGORIA
        category_name, category_initial, color = self._get_entity_category_info(instance)
        light_color = self._lighten_color(color, 0.95)  # Versione molto chiara per sfondo
        
        html_parts = []
        html_parts.append(f'<div class="instance-card" id="{link_id}" style="background: linear-gradient(to right, {light_color} 0%, white 100%); border-left: 4px solid {color};">')
        
        # Header
        html_parts.append(f'  <div class="card-header">')
        html_parts.append(f'    <div class="card-title">')
        html_parts.append(f'      <span class="instance-num">#{index}</span>')
        html_parts.append(f'      <span class="entity-badge" style="background-color: {color}; color: white;" title="{category_name}">{category_initial}</span>')
        html_parts.append(f'      <span class="instance-name">{self._escape(display_name)}</span>')
        html_parts.append(f'      <span class="instance-type">{self._escape(class_name)}</span>')
        html_parts.append(f'    </div>')
        html_parts.append(f'    <div class="instance-uri" title="{self._escape(identifier)}">{self._escape(identifier)}</div>')
        html_parts.append(f'  </div>')
        
        # Attributes
        html_parts.append(f'  <div class="card-body">')
        
        getters = [m for m in dir(instance) if m.startswith('get_') and callable(getattr(instance, m))]
        
        # Classifica proprietà
        props_by_type = {'strings': [], 'booleans': [], 'others': []}
        
        for getter_name in sorted(getters):
            try:
                getter_method = getattr(instance, getter_name)
                value = getter_method()
                
                if value is None or value == [] or value == '':
                    continue
                
                if isinstance(value, bool) and value is False:
                    continue
                
                field_name = getter_name.replace('get_', '').replace('has_', '').replace('_', ' ')
                
                if isinstance(value, str):
                    props_by_type['strings'].append((field_name, value))
                elif isinstance(value, bool):
                    props_by_type['booleans'].append((field_name, value))
                else:
                    props_by_type['others'].append((field_name, value))
            except:
                pass
        
        # Mostra proprietà nell'ordine
        for field_name, value in props_by_type['strings']:
            formatted_value = self._format_value(value)
            html_parts.append(f'    <div class="prop">')
            html_parts.append(f'      <span class="prop-name">{self._escape(field_name)}:</span>')
            html_parts.append(f'      <span class="prop-value">{formatted_value}</span>')
            html_parts.append(f'    </div>')
        
        for field_name, value in props_by_type['booleans']:
            formatted_value = self._format_value(value)
            html_parts.append(f'    <div class="prop">')
            html_parts.append(f'      <span class="prop-name">{self._escape(field_name)}:</span>')
            html_parts.append(f'      <span class="prop-value">{formatted_value}</span>')
            html_parts.append(f'    </div>')
        
        for field_name, value in props_by_type['others']:
            formatted_value = self._format_value(value)
            html_parts.append(f'    <div class="prop">')
            html_parts.append(f'      <span class="prop-name">{self._escape(field_name)}:</span>')
            html_parts.append(f'      <span class="prop-value">{formatted_value}</span>')
            html_parts.append(f'    </div>')
        
        html_parts.append(f'  </div>')
        
        # ✅ STATEMENTS INSTANCES (nested dentro questa card)
        related_statements = self.statement_instances_by_subject.get(identifier, [])
        if related_statements:
            accordion_id = f"statements-instances-{link_id}-{class_name}"
            statement_count = len(related_statements)
            
            html_parts.append(f'  <div class="statements-section">')
            html_parts.append(f'    <button class="accordion-toggle statements-toggle" onclick="toggleAccordion(\'{accordion_id}\')">')
            html_parts.append(f'      <span class="toggle-icon">▶</span>')
            html_parts.append(f'      <span class="toggle-text">Statements ({statement_count})</span>')
            html_parts.append(f'    </button>')
            html_parts.append(f'    <div class="accordion-content statements-content" id="{accordion_id}">')
            
            for stmt_idx, statement in enumerate(related_statements, 1):
                html_parts.append(self._generate_statement_html(statement, stmt_idx, link_id))
            
            html_parts.append(f'    </div>')
            html_parts.append(f'  </div>')
        
        # ✅ RDF STATEMENTS (solo dove questa istanza è il soggetto)
        statements = self.statements_by_subject.get(identifier, set())
        if statements:
            accordion_id = f"rdf-statements-{link_id}"
            statement_count = len(statements)
            
            html_parts.append(f'  <div class="triples-accordion">')
            html_parts.append(f'    <button class="accordion-toggle" onclick="toggleAccordion(\'{accordion_id}\')">')
            html_parts.append(f'      <span class="toggle-icon">▶</span>')
            html_parts.append(f'      <span class="toggle-text">RDF Statements ({statement_count})</span>')
            html_parts.append(f'    </button>')
            html_parts.append(f'    <div class="accordion-content" id="{accordion_id}">')
            
            # Ordina statements per predicato
            for subj, pred, obj in sorted(statements, key=lambda x: str(x[1])):
                subj_str = self._format_rdf_node(subj)
                pred_str = self._format_rdf_node(pred)
                obj_str = self._format_rdf_node(obj)
                
                html_parts.append(f'      <div class="triple-line">')
                html_parts.append(f'        <span class="triple-s">{subj_str}</span>')
                html_parts.append(f'        <span class="triple-p">{pred_str}</span>')
                html_parts.append(f'        <span class="triple-o">{obj_str}</span>')
                html_parts.append(f'        <span class="triple-dot">.</span>')
                html_parts.append(f'      </div>')
            
            html_parts.append(f'    </div>')
            html_parts.append(f'  </div>')
        
        html_parts.append(f'</div>')
        
        return '\n'.join(html_parts)

    def generate_full_html(self, output_path: str, ontology_url: str, title: str = "Ontology Browser"):
        """Genera un file HTML completo con CSS e JS esterni"""
        
        # Determina i path per CSS e JS nella stessa directory del generatore
        generator_dir = Path(__file__).parent
        css_path = generator_dir / "ontology_browser.css"
        js_path = generator_dir / "ontology_browser.js"
        
        # Fallback: cerca nella sottocartella templates
        if not css_path.exists():
            css_path = generator_dir / "templates" / "ontology_browser.css"
        if not js_path.exists():
            js_path = generator_dir / "templates" / "ontology_browser.js"
        
        # Leggi CSS e JS
        css_content = ""
        js_content = ""
        
        if css_path.exists():
            css_content = css_path.read_text(encoding='utf-8')
            print(f"  ✓ Loaded CSS from: {css_path}")
        else:
            print(f"  ⚠ CSS not found at: {css_path}")
            css_content = self._generate_fallback_css()
        
        if js_path.exists():
            js_content = js_path.read_text(encoding='utf-8')
            print(f"  ✓ Loaded JS from: {js_path}")
        else:
            print(f"  ⚠ JS not found at: {js_path}")
            js_content = self._generate_fallback_js()
        
        html_parts = []
        
        # Header
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="en">')
        html_parts.append('<head>')
        html_parts.append('  <meta charset="UTF-8">')
        html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append(f'  <title>{self._escape(title)}</title>')
        
        # CSS inline (o riferimento esterno se preferisci)
        html_parts.append('  <style>')
        html_parts.append(css_content)
        html_parts.append('  </style>')
        
        html_parts.append('</head>')
        html_parts.append('<body>')
        html_parts.append('  <div class="container">')
        
        # Title and info
        html_parts.append(f'    <h1>{self._escape(title)}</h1>')
        html_parts.append('    <div class="ontology-info">')
        html_parts.append(f'      <div><strong>Source:</strong> <code>{self._escape(ontology_url)}</code></div>')
        html_parts.append('      <div class="stats">')
        
        # Calcola statistiche escludendo Statement instances dalle card principali
        statement_class_names = set()
        for class_name, instances_list in self.instances.items():
            if instances_list and hasattr(instances_list[0], 'get_has_subject'):
                statement_class_names.add(class_name)
        
        total_instances = sum(len(instances) for class_name, instances in self.instances.items() if class_name not in statement_class_names)
        total_statements = sum(len(stmts) for stmts in self.statement_instances_by_subject.values())
        total_rdf_triples = sum(len(stmts) for stmts in self.statements_by_subject.values())
        
        html_parts.append(f'        <div class="stat">')
        html_parts.append(f'          <div class="stat-label">Instances</div>')
        html_parts.append(f'          <div class="stat-value">{total_instances}</div>')
        html_parts.append(f'        </div>')
        
        html_parts.append(f'        <div class="stat">')
        html_parts.append(f'          <div class="stat-label">Statements</div>')
        html_parts.append(f'          <div class="stat-value">{total_statements}</div>')
        html_parts.append(f'        </div>')
        
        html_parts.append(f'        <div class="stat">')
        html_parts.append(f'          <div class="stat-label">RDF Triples</div>')
        html_parts.append(f'          <div class="stat-value">{total_rdf_triples}</div>')
        html_parts.append(f'        </div>')
        
        html_parts.append('      </div>')
        html_parts.append('    </div>')
        
        # Navigation (escludi classi Statement)
        html_parts.append('    <nav class="nav">')

        for class_name in sorted(self.instances.keys()):
            if class_name not in statement_class_names:
                instances = self.instances[class_name]
                if not instances:
                    continue
                
                # ✨ OTTIENI COLORE PER QUESTA CLASSE
                sample_instance = instances[0]
                category_name, category_initial, color = self._get_entity_category_info(sample_instance)
                light_color = self._lighten_color(color, 0.85)
                
                html_parts.append(f'      <a href="#class-{class_name.lower()}" style="background: {light_color}; border-left: 3px solid {color};">')
                html_parts.append(f'        <span class="entity-badge" style="background-color: {color}; color: white;">{category_initial}</span>')
                html_parts.append(f'        {class_name}')
                html_parts.append(f'      </a>')

        html_parts.append('    </nav>')
        
        # Classes con griglia di instances (escludi Statement)
        for class_name in sorted(self.instances.keys()):
            if class_name in statement_class_names:
                continue  # Skippa le classi Statement
            
            instances = self.instances[class_name]
            if not instances:
                continue
            
            html_parts.append(f'    <div class="class-section" id="class-{class_name.lower()}">')
            html_parts.append(f'      <div class="class-header">')
            html_parts.append(f'        <span class="class-name">{self._escape(class_name)}</span>')
            html_parts.append(f'        <span class="class-count">{len(instances)} instances</span>')
            html_parts.append(f'      </div>')
            
            # Griglia di card
            html_parts.append(f'      <div class="instances-grid">')
            for i, instance in enumerate(instances, 1):
                html_parts.append(self._generate_instance_html(instance, i))
            html_parts.append(f'      </div>')
            
            html_parts.append(f'    </div>')
        
        # Footer
        html_parts.append('  </div>')
        
        # JavaScript inline
        html_parts.append('  <script>')
        html_parts.append(js_content)
        html_parts.append('  </script>')
        
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text('\n'.join(html_parts), encoding='utf-8')
        
        print(f"✓ HTML generated: {output_path}")
        print(f"  Total instances: {total_instances}")
        print(f"  Nested statements: {total_statements}")
        print(f"  RDF triples: {total_rdf_triples}")

    def _lighten_color(self, hex_color: str, amount: float = 0.9) -> str:
        """
        Schiarisce un colore hex
        amount: 0.0 (nero) -> 1.0 (bianco)
        """
        # Rimuovi il # se presente
        hex_color = hex_color.lstrip('#')
        
        # Converti in RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Schiarisci verso il bianco
        r = int(r + (255 - r) * amount)
        g = int(g + (255 - g) * amount)
        b = int(b + (255 - b) * amount)
        
        # Riconverti in hex
        return f'#{r:02x}{g:02x}{b:02x}'

def generate_custom_html(ontology_url: str, read_as: str = 'RDF', output_path: str = None, title: str = None):
    """
    Genera HTML per un'ontologia custom
    
    Args:
        ontology_url: URL o path dell'ontologia
        read_as: Formato ('OWL', 'SKOS', 'RDF', 'RDFS')
        output_path: Path output HTML (default: output/<filename>.html)
        title: Titolo HTML (default: "Ontology Browser - <url>")
    """
    
    if output_path is None:
        filename = ontology_url.split('/')[-1].replace('.', '_') + '.html'
        output_path = f"output/{filename}"
    
    if title is None:
        title = f"Ontology Browser - {ontology_url}"
    
    print(f"\n{'='*60}")
    print(f"GENERATING HTML FOR {ontology_url}")
    print(f"Format: {read_as}")
    print(f"{'='*60}\n")
    
    reader = Reader()
    reader.clear_cache()
    reader.load_instances(ontology_url, read_as=read_as)
    
    generator = OntologyHTMLGenerator(reader)
    generator.generate_full_html(
        output_path=output_path,
        ontology_url=ontology_url,
        title=title
    )
    
    print(f"\n{'='*60}")
    print(f"✓ Done! Open {output_path} in browser")
    print(f"{'='*60}\n")

# ========== TEST CASES ==========

def test_owl():
    """Test OWL con default domain/range"""
    print("\n🦉 TEST OWL")
    generate_custom_html(
        ontology_url="https://raw.githubusercontent.com/br0ast/ICON/main/Ontology/current/icon.rdf",
        read_as='OWL',
        output_path="output/test_owl.html",
        title="OWL Test - FOAF"
    )


def test_skos():
    """Test SKOS senza default"""
    print("\n📚 TEST SKOS")
    generate_custom_html(
        ontology_url="https://raw.githubusercontent.com/br0ast/ICON/main/Ontology/current/icon.rdf",
        read_as='SKOS',
        output_path="output/test_skos.html",
        title="SKOS Test - ICON"
    )


def test_rdf():
    """Test RDF puro con Statement"""
    print("\n📄 TEST RDF")
    generate_custom_html(
        ontology_url="https://raw.githubusercontent.com/br0ast/ICON/main/Ontology/current/icon.rdf",
        read_as='RDF',
        output_path="output/test_rdf.html",
        title="RDF Test - Core"
    )


def test_rdfs():
    """Test RDFS"""
    print("\n📋 TEST RDFS")
    generate_custom_html(
        ontology_url="http://www.w3.org/2000/01/rdf-schema#",
        read_as='RDF',
        output_path="output/test_rdfs.html",
        title="RDFS Test - Schema"
    )


def test_skos_to_skos():
    """Test RDFS"""
    print("\n📋 TEST SKOS TO SKOS")
    generate_custom_html(
        ontology_url="https://raw.githubusercontent.com/WenDAng-project/thesaurus/refs/heads/main/writeThesaurus_v.1.0.ttl",
        read_as='SKOS',
        output_path="output/test_skos_to_skos.html",
        title="Weng Dang Skos Test to SKOS"
    )

def test_skos_to_rdf():
    """Test RDFS"""
    print("\n📋 TEST SKOS TO RDF")
    generate_custom_html(
        ontology_url="https://raw.githubusercontent.com/WenDAng-project/thesaurus/refs/heads/main/writeThesaurus_v.1.0.ttl",
        read_as='RDF',
        output_path="output/test_skos_to_rdf.html",
        title="Weng Dang Skos Test to RDF"
    )

def test_pizza_owl_to_owl():
    """TEST PIZZA OWL TO OWL"""
    print("\n📋 TEST PIZZA OWL TO OWL")
    generate_custom_html(
        ontology_url="https://protege.stanford.edu/ontologies/pizza/pizza.owl",
        read_as='OWL',
        output_path="output/test_pizza__owl_to_owl.html",
        title="Pizza ontology OWL to OWL"
    )

def test_icon_owl_to_owl():
    """TEST ICON OWL TO OWL"""
    print("\n📋 TEST ICON OWL TO OWL")
    generate_custom_html(
        ontology_url="https://w3id.org/icon/ontology/",
        read_as='OWL',
        output_path="output/test_icon_owl_to_owl.html",
        title="ICON ontology OWL to OWL"
    )

def test_icon_owl_to_rdf():
    """TEST ICON OWL TO RDF"""
    print("\n📋 TEST ICON OWL TO RDF")
    generate_custom_html(
        ontology_url="https://w3id.org/icon/ontology/",
        read_as='RDF',
        output_path="output/test_icon_owl_to_rdf.html",
        title="ICON ontology OWL to RDF"
    )

def test_space_owl_to_owl():
    """TEST SPACE OWL TO OWL"""
    print("\n📋 TEST ICON OWL TO OWL")
    generate_custom_html(
        ontology_url="C:\\Users\\valep\\Documents\\GitHub\\lode2\\reader2\\test\\semantic_artefacts\\ontology_v2.0-rc2.owl", 
        read_as='OWL',
        output_path="output/test_space_owl_to_owl.html",
        title="SPACE ontology OWL to OWL"
    )

def test_owl_to_rdf():
    """Test RDFS"""
    print("\n📋 TEST OWL TO OWL")
    generate_custom_html(
        ontology_url="https://protege.stanford.edu/ontologies/pizza/pizza.owl",
        read_as='RDF',
        output_path="output/test_owl_to_rdf.html",
        title="Pizza ontology OWL to RDF"
    )

def test_owl_to_rdfs():
    """Test RDFS"""
    print("\n📋 TEST OWL TO RDFS")
    generate_custom_html(
        ontology_url="https://protege.stanford.edu/ontologies/pizza/pizza.owl",
        read_as='RDF',
        output_path="output/test_owl_to_rdfs.html",
        title="Pizza ontology OWL to RDFS"
    )

def test_owl_to_skos():
    """Test RDFS"""
    print("\n📋 TEST OWL TO OWL")
    generate_custom_html(
        ontology_url="https://protege.stanford.edu/ontologies/pizza/pizza.owl",
        read_as='SKOS',
        output_path="output/test_owl_to_skos.html",
        title="Pizza ontology OWL to SKOS"
    )

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test HTML Generator with nested statements')
    parser.add_argument('--test', choices=['owl', 'skos', 'rdf', 'rdfs', 'all'], 
                       default='all', help='Which test to run')
    
    args = parser.parse_args()
    
    if args.test == 'all':
        # test_owl()
        # test_skos()
        # test_rdf()
        # test_rdfs()

        try:
            test_icon_owl_to_owl()
        except Exception as e:
             raise Exception(e)
        try:
            test_icon_owl_to_rdf()
        except Exception as e:
            raise Exception(e)
        try:
            test_pizza_owl_to_owl()
        except Exception as e:
            raise Exception(e)
        try:
            test_space_owl_to_owl()
        except Exception as e:
            raise Exception(e)