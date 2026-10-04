import os
import re
import sys
import json
import argparse
from collections import defaultdict, deque

# Константы для исключения
EXCLUDED_DIRS = {'tests', '__pycache__', 'venv', '.git', 'docs', 'benchmarks'}
EXCLUDED_FILES = {'__init__.py'}

# Регулярное выражение для поиска импортов (абсолютных)
IMPORT_REGEX = re.compile(r'^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import|import\s+([a-zA-Z0-9_.]+))')

def find_python_files(root_dir):
    """Рекурсивно находит все .py файлы, исключая тесты и служебные директории."""
    py_files = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]
        for file in files:
            if file.endswith('.py') and file not in EXCLUDED_FILES:
                py_files.append(os.path.join(root, file))
    return py_files

def parse_imports(file_path, project_root):
    """Улучшенная версия: понимает относительные импорты (from . import X)."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if not line or not line.startswith(('from ', 'import ')):
                    continue

                # Обработка относительных импортов: from .module import X
                if line.startswith('from .'):
                    # Находим относительный путь текущего файла внутри проекта
                    current_dir = os.path.dirname(os.path.relpath(file_path, project_root))
                    # Считаем точки (уровень вложенности), вычитаем 1, так как первая точка идет после 'from'
                    dots = len([c for c in line if c == '.']) - 1 
                    
                    # Извлекаем имя модуля после точек
                    parts = line.split()
                    if len(parts) >= 4 and parts[2] == 'import':
                        module_name = parts[1][dots+1:] # отрезаем точки и первую точку
                    else:
                        continue
                    
                    # Собираем абсолютный путь внутри проекта
                    real_parts = current_dir.split(os.sep)[:len(current_dir.split(os.sep)) - dots] + [module_name]
                    clean_path = os.path.join(*[p for p in real_parts if p])
                    
                    # Проверяем, файл это или пакет
                    target_file = os.path.join(project_root, clean_path + '.py')
                    target_pkg = os.path.join(project_root, clean_path, '__init__.py')
                    
                    if os.path.exists(target_file):
                        imports.add(os.path.normpath(target_file))
                    elif os.path.exists(target_pkg):
                        imports.add(os.path.normpath(target_pkg))

                # Обработка абсолютных импортов: import X или from X import Y
                elif line.startswith('import ') or line.startswith('from '):
                    match = IMPORT_REGEX.search(line)
                    if match:
                        module_path = match.group(1) or match.group(2)
                        if not module_path or module_path.startswith('.'):
                            continue
                        
                        # Исключаем сторонние библиотеки (проверяем, есть ли папка в корне проекта)
                        top_level = module_path.split('.')[0]
                        if not os.path.isdir(os.path.join(project_root, top_level)):
                            continue
                        
                        if '.' in module_path:
                            target = os.path.join(project_root, *module_path.split('.'), '__init__.py')
                        else:
                            target = os.path.join(project_root, module_path + '.py')
                        
                        if os.path.exists(target):
                            imports.add(os.path.normpath(target))
    except (UnicodeDecodeError, PermissionError):
        pass
    return imports

def build_graph(root_dir):
    files = find_python_files(root_dir)
    adj = defaultdict(set)
    reverse_adj = defaultdict(set)
    
    for file_path in files:
        imports = parse_imports(file_path, root_dir)
        for imp in imports:
            if imp in files:
                adj[file_path].add(imp)
                reverse_adj[imp].add(file_path)
                
    for f in files:
        adj[f] = adj.get(f, set())
        reverse_adj[f] = reverse_adj.get(f, set())
        
    return files, adj, reverse_adj

def cmd_stats(files, adj, reverse_adj):
    v = len(files)
    e = sum(len(neighbors) for neighbors in adj.values())
    degrees = [len(adj[f]) for f in files]
    avg_degree = sum(degrees) / v if v > 0 else 0
    no_outgoing = sum(1 for f in files if not adj[f])
    no_incoming = sum(1 for f in files if not reverse_adj[f])
    
    index = 0
    stack = []
    indices = {}
    lowlink = {}
    on_stack = set()
    sccs = []
    
    def strongconnect(v_node):
        nonlocal index
        indices[v_node] = index
        lowlink[v_node] = index
        index += 1
        stack.append(v_node)
        on_stack.add(v_node)

        for w in adj[v_node]:
            if w not in indices:
                strongconnect(w)
                lowlink[v_node] = min(lowlink[v_node], lowlink[w])
            elif w in on_stack:
                lowlink[v_node] = min(lowlink[v_node], indices[w])

        if lowlink[v_node] == indices[v_node]:
            component = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.append(w)
                if w == v_node:
                    break
            sccs.append(component)

    for v_node in files:
        if v_node not in indices:
            strongconnect(v_node)
            
    return {
        'vertices': v,
        'edges': e,
        'avg_degree': round(avg_degree, 2),
        'no_outgoing': no_outgoing,
        'no_incoming': no_incoming,
        'scc_count': len(sccs)
    }

def cmd_impact(file_path, reverse_adj):
    if file_path not in reverse_adj:
        return {}
        
    visited = {file_path}
    queue = deque([(file_path, 0)])
    layers = defaultdict(set)
    
    while queue:
        current, depth = queue.popleft()
        for neighbor in reverse_adj[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                layers[depth + 1].add(neighbor)
                queue.append((neighbor, depth + 1))
                
    return dict(layers)

def cmd_cycles(files, adj):
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {f: WHITE for f in files}
    stack = []
    cycles = []
    
    def dfs(v):
        color[v] = GRAY
        stack.append(v)
        for w in adj[v]:
            if color[w] == WHITE:
                if dfs(w):
                    return True
            elif color[w] == GRAY:
                try:
                    idx = stack.index(w)
                    cycles.append(stack[idx:] + [w])
                except ValueError:
                    pass
                return True
        stack.pop()
        color[v] = BLACK
        return False

    for f in files:
        if color[f] == WHITE:
            if dfs(f):
                pass
    return cycles

def cmd_order(files, adj):
    in_degree = {f: 0 for f in files}
    for u in adj:
        for v in adj[u]:
            in_degree[v] += 1
            
    queue = deque([f for f in files if in_degree[f] == 0])
    layers = []
    
    while queue:
        current_layer = []
        for _ in range(len(queue)):
            u = queue.popleft()
            current_layer.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
        if current_layer:
            layers.append(current_layer)
            
    return layers

def main():
    parser = argparse.ArgumentParser(description='Dependency Graph Analyzer')
    subparsers = parser.add_subparsers(dest='command', required=True)

    stats_p = subparsers.add_parser('stats')
    stats_p.add_argument('path')

    impact_p = subparsers.add_parser('impact')
    impact_p.add_argument('path')
    impact_p.add_argument('file')

    cycles_p = subparsers.add_parser('cycles')
    cycles_p.add_argument('path')

    order_p = subparsers.add_parser('order')
    order_p.add_argument('path')

    args = parser.parse_args()
    
    root_dir = args.path
    if not os.path.isdir(root_dir):
        root_dir = os.path.join('scrapy', args.path)
        
    if not os.path.isdir(root_dir):
        print(f"Error: Directory {args.path} not found", file=sys.stderr)
        sys.exit(1)

    files, adj, reverse_adj = build_graph(root_dir)

    if args.command == 'stats':
        res = cmd_stats(files, adj, reverse_adj)
        print(f"Vertices (files): {res['vertices']}")
        print(f"Edges (imports): {res['edges']}")
        print(f"Average degree: {res['avg_degree']}")
        print(f"Files with no dependencies (sources): {res['no_outgoing']}")
        print(f"Files depending on nobody (sinks): {res['no_incoming']}")
        print(f"Weakly connected components (SCC): {res['scc_count']}")

    elif args.command == 'impact':
        norm_file = os.path.normpath(args.file)
        if not os.path.exists(norm_file):
            norm_file = os.path.normpath(os.path.join(root_dir, args.file))
            
        res = cmd_impact(norm_file, reverse_adj)
        if not res:
            print(f"No dependents found for {norm_file}")
        else:
            for depth in sorted(res.keys()):
                print(f"Layer {depth} ({len(res[depth])} files):")
                for f in sorted(res[depth]):
                    print(f"  {os.path.relpath(f, root_dir)}")

    elif args.command == 'cycles':
        res = cmd_cycles(files, adj)
        if res:
            sys.exit(1)
            for i, cycle in enumerate(res, 1):
                rel_paths = [os.path.relpath(f, root_dir) for f in cycle]
                print(f"Cycle {i}: {' -> '.join(rel_paths)}")
        else:
            print("No cycles found.")
            sys.exit(0)

    elif args.command == 'order':
        res = cmd_order(files, adj)
        print("Build order layers:")
        for i, layer in enumerate(res, 1):
            rel_paths = [os.path.relpath(f, root_dir) for f in layer]
            print(f"Batch {i} ({len(rel_paths)} files): {', '.join(rel_paths)}")
        print(f"Total batches: {len(res)}")
        print(f"Ratio to files: {len(res) / len(files):.2f}")

if __name__ == '__main__':
    main()