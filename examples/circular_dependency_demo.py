#!/usr/bin/env python3
"""
Unity Resource Reference Scanner - 循环依赖分析器示例

这个示例展示了如何使用循环依赖分析器来检测和分析Unity项目中的循环依赖关系。
"""

import logging
from pathlib import Path
import networkx as nx
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 模拟依赖图类
class MockDependencyGraph:
    """模拟的依赖图类，用于演示"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self._setup_sample_data()
    
    def _setup_sample_data(self):
        """设置示例数据"""
        # 创建一个包含多种循环类型的示例图
        edges = [
            # 简单循环: PlayerController -> UI -> GameManager -> PlayerController
            ('PlayerController', 'UI'),
            ('UI', 'GameManager'),
            ('GameManager', 'PlayerController'),
            
            # 复杂循环: Enemy -> AI -> Pathfinding -> Navigation -> CollisionSystem -> Physics -> Enemy
            ('Enemy', 'AI'),
            ('AI', 'Pathfinding'),
            ('Pathfinding', 'Navigation'),
            ('Navigation', 'CollisionSystem'),
            ('CollisionSystem', 'Physics'),
            ('Physics', 'Enemy'),
            
            # 自循环
            ('ConfigManager', 'ConfigManager'),
            
            # 嵌套循环: AudioManager -> SoundEffect -> AudioSource -> AudioListener -> AudioManager
            ('AudioManager', 'SoundEffect'),
            ('SoundEffect', 'AudioSource'),
            ('AudioSource', 'AudioListener'),
            ('AudioListener', 'AudioManager'),
            
            # 另一个简单循环: Inventory -> Item -> Equipment -> Inventory
            ('Inventory', 'Item'),
            ('Item', 'Equipment'),
            ('Equipment', 'Inventory'),
            
            # 一些非循环的边
            ('GameManager', 'Logger'),
            ('Logger', 'FileSystem'),
            ('UI', 'InputSystem'),
        ]
        
        self.graph.add_edges_from(edges)
        
        # 添加节点数据
        node_data = {
            'PlayerController': {'asset_type': 'script', 'size': 1500},
            'UI': {'asset_type': 'prefab', 'size': 800},
            'GameManager': {'asset_type': 'script', 'size': 2000},
            'Enemy': {'asset_type': 'prefab', 'size': 1200},
            'AI': {'asset_type': 'script', 'size': 1800},
            'Pathfinding': {'asset_type': 'script', 'size': 2200},
            'Navigation': {'asset_type': 'script', 'size': 1000},
            'CollisionSystem': {'asset_type': 'script', 'size': 1600},
            'Physics': {'asset_type': 'script', 'size': 3000},
            'ConfigManager': {'asset_type': 'script', 'size': 500},
            'AudioManager': {'asset_type': 'script', 'size': 1400},
            'SoundEffect': {'asset_type': 'asset', 'size': 300},
            'AudioSource': {'asset_type': 'component', 'size': 200},
            'AudioListener': {'asset_type': 'component', 'size': 150},
            'Inventory': {'asset_type': 'script', 'size': 1100},
            'Item': {'asset_type': 'scriptableobject', 'size': 400},
            'Equipment': {'asset_type': 'scriptableobject', 'size': 600},
            'Logger': {'asset_type': 'script', 'size': 300},
            'FileSystem': {'asset_type': 'script', 'size': 700},
            'InputSystem': {'asset_type': 'script', 'size': 900},
        }
        
        for node, data in node_data.items():
            if node in self.graph:
                self.graph.nodes[node].update(data)
        
        # 添加边数据
        edge_data = {
            ('PlayerController', 'UI'): {'dependency_strength': 'strong', 'dependency_type': 'component'},
            ('UI', 'GameManager'): {'dependency_strength': 'medium', 'dependency_type': 'reference'},
            ('GameManager', 'PlayerController'): {'dependency_strength': 'weak', 'dependency_type': 'reference'},
            ('Enemy', 'AI'): {'dependency_strength': 'critical', 'dependency_type': 'component'},
            ('AI', 'Pathfinding'): {'dependency_strength': 'important', 'dependency_type': 'script'},
            ('Pathfinding', 'Navigation'): {'dependency_strength': 'medium', 'dependency_type': 'reference'},
            ('Navigation', 'CollisionSystem'): {'dependency_strength': 'important', 'dependency_type': 'physics'},
            ('CollisionSystem', 'Physics'): {'dependency_strength': 'critical', 'dependency_type': 'engine'},
            ('Physics', 'Enemy'): {'dependency_strength': 'medium', 'dependency_type': 'collision'},
            ('ConfigManager', 'ConfigManager'): {'dependency_strength': 'strong', 'dependency_type': 'self'},
            ('AudioManager', 'SoundEffect'): {'dependency_strength': 'medium', 'dependency_type': 'asset'},
            ('SoundEffect', 'AudioSource'): {'dependency_strength': 'strong', 'dependency_type': 'component'},
            ('AudioSource', 'AudioListener'): {'dependency_strength': 'weak', 'dependency_type': 'audio'},
            ('AudioListener', 'AudioManager'): {'dependency_strength': 'medium', 'dependency_type': 'reference'},
            ('Inventory', 'Item'): {'dependency_strength': 'strong', 'dependency_type': 'data'},
            ('Item', 'Equipment'): {'dependency_strength': 'medium', 'dependency_type': 'inheritance'},
            ('Equipment', 'Inventory'): {'dependency_strength': 'weak', 'dependency_type': 'reference'},
        }
        
        for (source, target), data in edge_data.items():
            if self.graph.has_edge(source, target):
                self.graph[source][target].update(data)
    
    def find_circular_dependencies(self):
        """模拟原始的循环检测方法"""
        cycles = []
        try:
            sccs = list(nx.strongly_connected_components(self.graph))
            for scc in sccs:
                if len(scc) > 1:
                    nodes = list(scc)
                    cycle = nodes + [nodes[0]]
                    cycles.append(cycle)
                elif len(scc) == 1:
                    node = list(scc)[0]
                    if self.graph.has_edge(node, node):
                        cycles.append([node, node])
        except Exception as e:
            logger.error(f"循环检测失败: {e}")
        return cycles
    
    def get_node_data(self, node: str):
        """获取节点数据"""
        if node in self.graph:
            return self.graph.nodes[node]
        return None
    
    def get_edge_data(self, source: str, target: str):
        """获取边数据"""
        if self.graph.has_edge(source, target):
            return self.graph[source][target]
        return None
    
    def has_edge(self, source: str, target: str):
        """检查边是否存在"""
        return self.graph.has_edge(source, target)
    
    def get_predecessors(self, node: str):
        """获取前驱节点"""
        return list(self.graph.predecessors(node))
    
    def get_successors(self, node: str):
        """获取后继节点"""
        return list(self.graph.successors(node))
    
    def get_node_count(self):
        """获取节点数量"""
        return self.graph.number_of_nodes()
    
    def get_edge_count(self):
        """获取边数量"""
        return self.graph.number_of_edges()


def demonstrate_circular_dependency_analysis():
    """演示循环依赖分析功能"""
    print("=" * 80)
    print("Unity Resource Reference Scanner - 循环依赖分析器演示")
    print("=" * 80)
    print()
    
    # 创建模拟的依赖图
    print("1. 创建示例依赖图...")
    dependency_graph = MockDependencyGraph()
    print(f"   图中包含 {dependency_graph.get_node_count()} 个节点和 {dependency_graph.get_edge_count()} 条边")
    print()
    
    # 导入循环依赖分析器
    from src.core.circular_dependency_analyzer import CircularDependencyAnalyzer
    
    # 创建分析器
    print("2. 创建循环依赖分析器...")
    analyzer = CircularDependencyAnalyzer(dependency_graph)
    print("   分析器创建完成")
    print()
    
    # 执行基本循环检测
    print("3. 执行基本循环检测...")
    basic_cycles = analyzer.detect_all_cycles(use_enhanced_detection=False)
    print(f"   检测到 {len(basic_cycles)} 个循环依赖:")
    for i, cycle in enumerate(basic_cycles, 1):
        print(f"   循环 {i}: {' -> '.join(cycle)}")
    print()
    
    # 执行增强循环检测
    print("4. 执行增强循环检测...")
    enhanced_cycles = analyzer.detect_all_cycles(use_enhanced_detection=True)
    print(f"   增强检测发现 {len(enhanced_cycles)} 个循环依赖")
    print()
    
    # 执行完整分析
    print("5. 执行完整的循环依赖分析...")
    start_time = datetime.now()
    report = analyzer.perform_full_analysis()
    analysis_time = datetime.now() - start_time
    
    print(f"   分析完成，耗时: {analysis_time.total_seconds():.3f} 秒")
    print(f"   总循环数: {report.total_cycles}")
    print(f"   受影响节点: {len(report.affected_nodes)}")
    print()
    
    # 显示循环分布统计
    print("6. 循环类型分布:")
    for cycle_type, count in report.cycle_distribution.items():
        print(f"   {cycle_type}: {count}")
    print()
    
    print("7. 严重程度分布:")
    for severity, count in report.severity_distribution.items():
        print(f"   {severity}: {count}")
    print()
    
    # 显示热点节点
    if report.hotspot_nodes:
        print("8. 热点节点 (出现在多个循环中):")
        for node, count in report.hotspot_nodes[:5]:
            print(f"   {node}: 出现在 {count} 个循环中")
        print()
    
    # 显示最严重的循环
    if report.most_critical_cycle:
        print("9. 最严重的循环:")
        cycle = report.most_critical_cycle
        print(f"   循环ID: {cycle.cycle_id}")
        print(f"   类型: {cycle.cycle_type.display_name}")
        print(f"   严重程度: {cycle.severity.display_name}")
        print(f"   长度: {cycle.length}")
        print(f"   路径: {' -> '.join(cycle.nodes)}")
        print("   修复建议:")
        for suggestion in cycle.suggested_fixes:
            print(f"     - {suggestion}")
        print()
    
    # 生成文本报告
    print("10. 生成文本报告...")
    text_report = analyzer.generate_cycle_report(report, format_type="text")
    
    # 保存报告到文件
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    report_file = output_dir / f"circular_dependency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(text_report)
    
    print(f"    文本报告已保存到: {report_file}")
    
    # 生成Markdown报告
    markdown_report = analyzer.generate_cycle_report(report, format_type="markdown")
    markdown_file = output_dir / f"circular_dependency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(markdown_file, 'w', encoding='utf-8') as f:
        f.write(markdown_report)
    
    print(f"    Markdown报告已保存到: {markdown_file}")
    
    # 生成JSON报告
    json_report = analyzer.generate_cycle_report(report, format_type="json")
    json_file = output_dir / f"circular_dependency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        f.write(json_report)
    
    print(f"    JSON报告已保存到: {json_file}")
    print()
    
    # 演示增量分析
    print("11. 演示增量分析...")
    changed_nodes = {'PlayerController', 'UI'}
    changed_edges = {('PlayerController', 'UI')}
    
    incremental_report = analyzer.get_incremental_analysis(changed_nodes, changed_edges)
    print(f"    增量分析发现 {incremental_report.total_cycles} 个循环")
    print(f"    分析算法: {incremental_report.detection_algorithm}")
    print(f"    分析耗时: {incremental_report.analysis_time_seconds:.3f} 秒")
    print()
    
    print("=" * 80)
    print("循环依赖分析演示完成!")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_circular_dependency_analysis()
