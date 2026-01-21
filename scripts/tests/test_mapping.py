"""
HTML Generator per ontologie RDF - VERSIONE COMPATTA
Genera pagine HTML navigabili dalle istanze caricate
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reader.orchestrator import Reader
from reader.models import *
from typing import Dict, List, Any
import html


class OntologyHTMLGenerator:
    """Genera HTML da istanze di ontologie"""
    
    def __init__(self, reader: Reader):
        self.reader = reader
        self.instances = reader.get_instances()
        
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
    
    def _format_single_item(self, item: Any) -> str:
        """Formatta un singolo item"""
        
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
                
                # Badges più compatti
                badges = []
                if lang:
                    badges.append(f'<span class="badge lang">{lang}</span>')
                if datatype:
                    badges.append(f'<span class="badge type">{datatype}</span>')
                
                badge_html = ''.join(badges)
                return f'<span class="literal">"{escaped_value}"{badge_html}</span>'
            except Exception as e:
                return f'<span class="literal error">Error: {e}</span>'
        
        # Tipi primitivi Python
        if isinstance(item, (bool, int, float)):
            value_str = str(item)
            type_name = type(item).__name__
            return f'<span class="primitive">{value_str}<span class="badge type">{type_name}</span></span>'
        
        if isinstance(item, str):
            escaped_value = self._escape(item)
            return f'<span class="primitive">"{escaped_value}"<span class="badge type">str</span></span>'
        
        # Resource con identifier
        if hasattr(item, 'get_has_identifier'):
            try:
                identifier = item.get_has_identifier()
                class_name = type(item).__name__
                link_id = identifier.replace(':', '_').replace('/', '_').replace('#', '_')
                
                # Nome più compatto per il link
                display_name = identifier.split('/')[-1].split('#')[-1] if identifier else class_name
                
                return f'<a href="#{link_id}" class="resource-link" title="{self._escape(identifier)}">{self._escape(display_name)}</a>'
            except:
                pass
        
        return f'<span class="resource">{self._escape(type(item).__name__)}</span>'

    def _generate_instance_html(self, instance: Any, index: int) -> str:
        """Genera HTML per una singola istanza - VERSIONE COMPATTA"""
        
        class_name = type(instance).__name__
        identifier = instance.get_has_identifier()
        
        if identifier is None:
            identifier = f"_blank_node_{id(instance)}"
            link_id = f"blank_{index}_{id(instance)}"
        else:
            link_id = identifier.replace(':', '_').replace('/', '_').replace('#', '_')
        
        # Nome più leggibile per l'header
        display_name = identifier.split('/')[-1].split('#')[-1] if identifier and identifier != f"_blank_node_{id(instance)}" else f"Instance {index}"
        
        html_parts = []
        html_parts.append(f'<div class="instance-card" id="{link_id}">')
        
        # Header compatto
        html_parts.append(f'  <div class="card-header">')
        html_parts.append(f'    <div class="card-title">')
        html_parts.append(f'      <span class="instance-num">#{index}</span>')
        html_parts.append(f'      <span class="instance-name">{self._escape(display_name)}</span>')
        html_parts.append(f'      <span class="instance-type">{self._escape(class_name)}</span>')
        html_parts.append(f'    </div>')
        html_parts.append(f'    <div class="instance-uri" title="{self._escape(identifier)}">{self._escape(identifier)}</div>')
        html_parts.append(f'  </div>')
        
        # Attributes compatti
        html_parts.append(f'  <div class="card-body">')
        
        getters = [m for m in dir(instance) if m.startswith('get_') and callable(getattr(instance, m))]
        
        for getter_name in sorted(getters):
            try:
                getter_method = getattr(instance, getter_name)
                value = getter_method()
                
                if value is None or value == [] or value == '':
                    continue
                
                field_name = getter_name.replace('get_', '').replace('has_', '').replace('_', ' ')
                formatted_value = self._format_value(value)
                
                html_parts.append(f'    <div class="prop">')
                html_parts.append(f'      <span class="prop-name">{self._escape(field_name)}:</span>')
                html_parts.append(f'      <span class="prop-value">{formatted_value}</span>')
                html_parts.append(f'    </div>')
            except:
                pass
        
        html_parts.append(f'  </div>')
        html_parts.append(f'</div>')
        
        return '\n'.join(html_parts) 

    def _generate_css(self) -> str:
        """Genera CSS compatto e moderno"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: #2c3e50;
            background: #f8f9fa;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        h1 {
            color: #1a202c;
            margin-bottom: 8px;
            font-size: 28px;
            font-weight: 700;
        }
        
        .ontology-info {
            background: #f7fafc;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 20px;
            border-left: 3px solid #4299e1;
            font-size: 13px;
        }
        
        .ontology-info code {
            background: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 12px;
            color: #4a5568;
        }
        
        .stats {
            display: flex;
            gap: 12px;
            margin-top: 10px;
        }
        
        .stat {
            background: white;
            padding: 8px 14px;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
        }
        
        .stat-label {
            font-size: 11px;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .stat-value {
            font-size: 20px;
            font-weight: 700;
            color: #2d3748;
            margin-top: 2px;
        }
        
        .nav {
            background: #2d3748;
            padding: 10px 16px;
            margin-bottom: 24px;
            border-radius: 6px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        
        .nav a {
            color: white;
            text-decoration: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
            transition: background 0.2s;
        }
        
        .nav a:hover {
            background: rgba(255,255,255,0.15);
        }
        
        .class-section {
            margin-bottom: 32px;
        }
        
        .class-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .class-name {
            font-size: 18px;
            font-weight: 600;
        }
        
        .class-count {
            background: rgba(255,255,255,0.25);
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        
        /* CARD LAYOUT - Griglia compatta */
        .instances-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 16px;
        }
        
        .instance-card {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            overflow: hidden;
            transition: all 0.2s;
        }
        
        .instance-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        
        .card-header {
            background: #f7fafc;
            padding: 12px 16px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .card-title {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }
        
        .instance-num {
            background: #edf2f7;
            color: #4a5568;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        }
        
        .instance-name {
            font-weight: 600;
            color: #2d3748;
            font-size: 14px;
        }
        
        .instance-type {
            background: #667eea;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 500;
            margin-left: auto;
        }
        
        .instance-uri {
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            font-size: 11px;
            color: #718096;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .card-body {
            padding: 14px 16px;
        }
        
        .prop {
            margin-bottom: 10px;
            display: flex;
            gap: 8px;
            font-size: 13px;
        }
        
        .prop:last-child {
            margin-bottom: 0;
        }
        
        .prop-name {
            font-weight: 600;
            color: #4a5568;
            min-width: 120px;
            flex-shrink: 0;
        }
        
        .prop-value {
            color: #2d3748;
            word-break: break-word;
        }
        
        .value-list {
            list-style: none;
            margin: 4px 0 0 0;
        }
        
        .value-list li {
            padding: 4px 0 4px 12px;
            border-left: 2px solid #cbd5e0;
            margin: 2px 0;
            font-size: 13px;
        }
        
        /* Badges compatti */
        .badge {
            display: inline-block;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 3px;
            margin-left: 4px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        
        .badge.lang {
            background: #fc8181;
            color: white;
        }
        
        .badge.type {
            background: #b794f4;
            color: white;
        }
        
        .literal {
            color: #38a169;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 13px;
        }
        
        .primitive {
            color: #805ad5;
            font-family: 'SF Mono', Monaco, monospace;
            font-weight: 600;
        }
        
        .resource-link {
            color: #3182ce;
            text-decoration: none;
            font-family: 'SF Mono', Monaco, monospace;
            padding: 2px 6px;
            border-radius: 3px;
            background: #ebf8ff;
            font-size: 12px;
            font-weight: 500;
        }
        
        .resource-link:hover {
            background: #3182ce;
            color: white;
        }
        
        .empty {
            color: #a0aec0;
            font-style: italic;
            font-size: 12px;
        }
        
        .error {
            color: #f56565;
            font-size: 12px;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .instances-grid {
                grid-template-columns: 1fr;
            }
            
            .prop {
                flex-direction: column;
                gap: 4px;
            }
            
            .prop-name {
                min-width: unset;
            }
        }
        """
    
    def generate_full_html(self, output_path: str, ontology_url: str, title: str = "Ontology Browser"):
        """Genera un file HTML completo con layout a griglia"""
        
        html_parts = []
        
        # Header
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="en">')
        html_parts.append('<head>')
        html_parts.append('  <meta charset="UTF-8">')
        html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append(f'  <title>{self._escape(title)}</title>')
        html_parts.append('  <style>')
        html_parts.append(self._generate_css())
        html_parts.append('  </style>')
        html_parts.append('</head>')
        html_parts.append('<body>')
        html_parts.append('  <div class="container">')
        
        # Title and info
        html_parts.append(f'    <h1>{self._escape(title)}</h1>')
        html_parts.append('    <div class="ontology-info">')
        html_parts.append(f'      <div><strong>Source:</strong> <code>{self._escape(ontology_url)}</code></div>')
        html_parts.append('      <div class="stats">')
        
        total_instances = sum(len(instances) for instances in self.instances.values())
        html_parts.append(f'        <div class="stat">')
        html_parts.append(f'          <div class="stat-label">Instances</div>')
        html_parts.append(f'          <div class="stat-value">{total_instances}</div>')
        html_parts.append(f'        </div>')
        
        html_parts.append(f'        <div class="stat">')
        html_parts.append(f'          <div class="stat-label">Classes</div>')
        html_parts.append(f'          <div class="stat-value">{len(self.instances)}</div>')
        html_parts.append(f'        </div>')
        
        html_parts.append('      </div>')
        html_parts.append('    </div>')
        
        # Navigation
        html_parts.append('    <nav class="nav">')
        for class_name in sorted(self.instances.keys()):
            html_parts.append(f'      <a href="#class-{class_name.lower()}">{class_name}</a>')
        html_parts.append('    </nav>')
        
        # Classes con griglia di instances
        for class_name in sorted(self.instances.keys()):
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
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text('\n'.join(html_parts), encoding='utf-8')
        
        print(f"✓ HTML generated: {output_path}")
        print(f"  Total instances: {total_instances}")
        print(f"  Classes: {len(self.instances)}")


# [Resto delle funzioni helper identico...]

def generate_custom_html(ontology_url: str, read_as: str = 'rdf', output_path: str = None, title: str = None):
    """Genera HTML per un'ontologia custom"""
    
    if output_path is None:
        filename = ontology_url.split('/')[-1].replace('.', '_') + '.html'
        output_path = f"output/{filename}"
    
    if title is None:
        title = f"Ontology Browser - {ontology_url}"
    
    print(f"\n=== Generating HTML for {ontology_url} ===\n")
    
    reader = Reader()
    reader.clear_cache()
    reader.load_instances(ontology_url, read_as=read_as)
    
    generator = OntologyHTMLGenerator(reader)
    generator.generate_full_html(
        output_path=output_path,
        ontology_url=ontology_url,
        title=title
    )


if __name__ == "__main__":
    reader = Reader()
    reader.clear_cache()
    reader.load_instances(
        "https://raw.githubusercontent.com/br0ast/ICON/main/Ontology/current/icon.rdf",
        read_as='owl'
    )
    
    generator = OntologyHTMLGenerator(reader)
    generator.generate_full_html(
        output_path="output/foaf_ontology.html",
        ontology_url="https://gist.githubusercontent.com/baskaufs/fefa1bfbff14a9efc174/raw/389e4b003ef5cbd6901dd8ab8a692b501bc9370e/foaf.ttl",
        title="FOAF Ontology Browser"
    )