import os
import sys
import subprocess
import networkx as nx
from dependency_analyzer import find_python_files, parse_imports, build_graph

PROJECT_ROOT = 'scrapy'

def main():
    print("Building graph via custom utility...")
    files, adj, _ = build_graph(PROJECT_ROOT)
    
    # Собираем ребра для networkx
    edges = []
    for u in adj:
        for v in adj[u]:
            edges.append((u, v))
            
    G = nx.DiGraph()
    G.add_nodes_from(files)
    G.add_edges_from(edges)
    
    # 1. Проверка циклов
    print("\n[Verify] Checking cycles...")
    nx_cycles = list(nx.simple_cycles(G))
    print(f"networkx found {len(nx_cycles)} cycles.")
    
    # Запускаем нашу утилиту
    result = subprocess.run([sys.executable, 'dependency_analyzer.py', 'cycles', PROJECT_ROOT], 
                            capture_output=True, text=True)
    my_cycles = result.stdout
    my_exit = result.returncode
    
    if (len(nx_cycles) > 0 and my_exit == 1) or (len(nx_cycles) == 0 and my_exit == 0):
        print("VERDICT: CYCLES CHECK PASSED")
    else:
        print("VERDICT: CYCLES CHECK FAILED")
        print("Our output:", my_cycles)

    # 2. Проверка топологического порядка
    print("\n[Verify] Checking topological order...")
    nx_order = list(nx.topological_generations(G))
    result = subprocess.run([sys.executable, 'dependency_analyzer.py', 'order', PROJECT_ROOT], 
                            capture_output=True, text=True)
    my_order_layers = [line for line in result.stdout.split('\n') if line.startswith('Batch')]
    
    if len(nx_order) == len(my_order_layers):
        print("VERDICT: TOPOLOGICAL ORDER PASSED")
    else:
        print("VERDICT: TOPOLOGICAL ORDER FAILED")
        print(f"networkx: {len(nx_order)} layers, ours: {len(my_order_layers)}")

if __name__ == '__main__':
    main()