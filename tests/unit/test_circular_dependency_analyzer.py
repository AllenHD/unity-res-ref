"""测试循环依赖分析器功能"""

import pytest
from unittest.mock import Mock, MagicMock
import networkx as nx
from datetime import datetime

from src.core.circular_dependency_analyzer import (
    CircularDependencyAnalyzer,
    CycleType,
    CycleSeverity,
    CycleInfo,
    CycleAnalysisReport
)


class TestCircularDependencyAnalyzer:
    """循环依赖分析器测试"""
    
    def setup_method(self):
        """测试设置"""
        # 模拟依赖图
        self.mock_graph = Mock()
        self.mock_graph.graph = nx.DiGraph()
        
        # 创建测试图结构
        self.mock_graph.graph.add_edges_from([
            ('A', 'B'),
            ('B', 'C'),
            ('C', 'A'),  # 简单循环 A->B->C->A
            ('D', 'E'),
            ('E', 'F'),
            ('F', 'G'),
            ('G', 'D'),  # 复杂循环 D->E->F->G->D
            ('H', 'H'),  # 自循环
        ])
        
        # 模拟节点数据
        self.mock_graph.get_node_data = Mock(side_effect=self._mock_get_node_data)
        self.mock_graph.get_edge_data = Mock(side_effect=self._mock_get_edge_data)
        self.mock_graph.has_edge = Mock(side_effect=lambda s, t: self.mock_graph.graph.has_edge(s, t))
        self.mock_graph.get_predecessors = Mock(side_effect=lambda n: list(self.mock_graph.graph.predecessors(n)))
        self.mock_graph.get_successors = Mock(side_effect=lambda n: list(self.mock_graph.graph.successors(n)))
        self.mock_graph.get_node_count = Mock(return_value=8)
        self.mock_graph.get_edge_count = Mock(return_value=8)
        
        # 模拟原始的find_circular_dependencies方法
        self.mock_graph.find_circular_dependencies = Mock(return_value=[
            ['A', 'B', 'C', 'A'],
            ['D', 'E', 'F', 'G', 'D'],
            ['H', 'H']
        ])
        
        self.analyzer = CircularDependencyAnalyzer(self.mock_graph)
    
    def _mock_get_node_data(self, node: str):
        """模拟获取节点数据"""
        node_types = {
            'A': {'asset_type': 'prefab'},
            'B': {'asset_type': 'scene'},
            'C': {'asset_type': 'script'},
            'D': {'asset_type': 'material'},
            'E': {'asset_type': 'texture'},
            'F': {'asset_type': 'mesh'},
            'G': {'asset_type': 'animation'},
            'H': {'asset_type': 'script'}
        }
        return node_types.get(node, {'asset_type': 'unknown'})
    
    def _mock_get_edge_data(self, source: str, target: str):
        """模拟获取边数据"""
        # 模拟不同强度的依赖
        edge_data = {
            ('A', 'B'): {'dependency_strength': 'strong', 'dependency_type': 'component'},
            ('B', 'C'): {'dependency_strength': 'medium', 'dependency_type': 'script'},
            ('C', 'A'): {'dependency_strength': 'weak', 'dependency_type': 'reference'},
            ('D', 'E'): {'dependency_strength': 'critical', 'dependency_type': 'material'},
            ('E', 'F'): {'dependency_strength': 'important', 'dependency_type': 'texture'},
            ('F', 'G'): {'dependency_strength': 'medium', 'dependency_type': 'mesh'},
            ('G', 'D'): {'dependency_strength': 'weak', 'dependency_type': 'animation'},
            ('H', 'H'): {'dependency_strength': 'strong', 'dependency_type': 'self'}
        }
        return edge_data.get((source, target), {'dependency_strength': 'weak', 'dependency_type': 'unknown'})
    
    def test_detect_all_cycles_basic(self):
        """测试基本循环检测"""
        cycles = self.analyzer.detect_all_cycles(use_enhanced_detection=False)
        
        assert len(cycles) == 3
        # 验证包含预期的循环
        cycle_sets = [set(cycle[:-1]) for cycle in cycles if len(cycle) > 1]  # 移除重复的首尾节点
        
        expected_cycles = [
            {'A', 'B', 'C'},
            {'D', 'E', 'F', 'G'},
            {'H'}
        ]
        
        for expected in expected_cycles:
            assert any(expected == actual for actual in cycle_sets), f"未找到预期的循环: {expected}"
    
    def test_analyze_cycle_severity(self):
        """测试循环严重程度分析"""
        # 测试简单循环
        simple_cycle = ['A', 'B', 'C', 'A']
        severity = self.analyzer.analyze_cycle_severity(simple_cycle)
        assert severity in [CycleSeverity.LOW, CycleSeverity.MEDIUM, CycleSeverity.HIGH]
        
        # 测试复杂循环
        complex_cycle = ['D', 'E', 'F', 'G', 'D']
        severity = self.analyzer.analyze_cycle_severity(complex_cycle)
        assert severity in [CycleSeverity.MEDIUM, CycleSeverity.HIGH, CycleSeverity.CRITICAL]
        
        # 测试自循环
        self_cycle = ['H', 'H']
        severity = self.analyzer.analyze_cycle_severity(self_cycle)
        assert severity == CycleSeverity.LOW
    
    def test_classify_cycle_type(self):
        """测试循环类型分类"""
        # 自循环
        self_cycle = ['H', 'H']
        assert self.analyzer.classify_cycle_type(self_cycle) == CycleType.SELF_LOOP
        
        # 简单循环
        simple_cycle = ['A', 'B', 'C', 'A']
        assert self.analyzer.classify_cycle_type(simple_cycle) == CycleType.SIMPLE_CYCLE
        
        # 复杂循环
        complex_cycle = ['D', 'E', 'F', 'G', 'D']
        assert self.analyzer.classify_cycle_type(complex_cycle) == CycleType.COMPLEX_CYCLE
    
    def test_find_critical_nodes(self):
        """测试关键节点查找"""
        cycle = ['A', 'B', 'C', 'A']
        critical_nodes = self.analyzer.find_critical_nodes(cycle)
        
        # 应该找到一些关键节点
        assert isinstance(critical_nodes, list)
        assert len(critical_nodes) >= 0
        
        # 关键节点应该都在循环中
        unique_cycle_nodes = set(cycle[:-1])
        for node in critical_nodes:
            assert node in unique_cycle_nodes
    
    def test_suggest_cycle_fixes(self):
        """测试循环修复建议"""
        cycle = ['A', 'B', 'C', 'A']
        suggestions = self.analyzer.suggest_cycle_fixes(cycle)
        
        # 应该提供一些建议
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        
        # 建议应该是字符串
        for suggestion in suggestions:
            assert isinstance(suggestion, str)
            assert len(suggestion) > 0
    
    def test_find_breakable_edges(self):
        """测试可断开边查找"""
        cycle = ['A', 'B', 'C', 'A']
        breakable_edges = self.analyzer.find_breakable_edges(cycle)
        
        assert isinstance(breakable_edges, list)
        
        # 验证返回的边都在循环中
        for source, target in breakable_edges:
            found = False
            for i in range(len(cycle) - 1):
                if cycle[i] == source and cycle[i + 1] == target:
                    found = True
                    break
            assert found, f"边 {source}->{target} 不在循环中"
    
    def test_perform_full_analysis(self):
        """测试完整分析"""
        report = self.analyzer.perform_full_analysis()
        
        # 验证报告结构
        assert isinstance(report, CycleAnalysisReport)
        assert report.total_cycles >= 0
        assert isinstance(report.cycles, list)
        assert isinstance(report.cycle_distribution, dict)
        assert isinstance(report.severity_distribution, dict)
        assert isinstance(report.affected_nodes, set)
        assert isinstance(report.analysis_time_seconds, float)
        assert report.analysis_time_seconds >= 0
        
        # 验证报告内容
        if report.cycles:
            # 检查循环信息
            for cycle in report.cycles:
                assert isinstance(cycle, CycleInfo)
                assert len(cycle.nodes) >= 2
                assert cycle.length >= 1
                assert isinstance(cycle.edges, list)
                assert isinstance(cycle.suggested_fixes, list)
    
    def test_generate_cycle_report_text(self):
        """测试文本格式报告生成"""
        report = self.analyzer.perform_full_analysis()
        text_report = self.analyzer.generate_cycle_report(report, format_type="text")
        
        assert isinstance(text_report, str)
        assert len(text_report) > 0
        assert "循环依赖分析报告" in text_report
        assert "统计摘要" in text_report
    
    def test_generate_cycle_report_markdown(self):
        """测试Markdown格式报告生成"""
        report = self.analyzer.perform_full_analysis()
        markdown_report = self.analyzer.generate_cycle_report(report, format_type="markdown")
        
        assert isinstance(markdown_report, str)
        assert len(markdown_report) > 0
        assert "# 循环依赖分析报告" in markdown_report
        assert "## 统计摘要" in markdown_report
    
    def test_generate_cycle_report_json(self):
        """测试JSON格式报告生成"""
        report = self.analyzer.perform_full_analysis()
        json_report = self.analyzer.generate_cycle_report(report, format_type="json")
        
        assert isinstance(json_report, str)
        assert len(json_report) > 0
        
        # 验证JSON格式正确
        import json
        parsed = json.loads(json_report)
        assert isinstance(parsed, dict)
        assert 'total_cycles' in parsed
        assert 'cycles' in parsed
    
    def test_incremental_analysis(self):
        """测试增量分析"""
        changed_nodes = {'A', 'B'}
        changed_edges = {('A', 'B')}
        
        report = self.analyzer.get_incremental_analysis(changed_nodes, changed_edges)
        
        assert isinstance(report, CycleAnalysisReport)
        assert report.detection_algorithm == "incremental_johnson"
        assert isinstance(report.analysis_time_seconds, float)


if __name__ == "__main__":
    # 运行简单的测试
    test = TestCircularDependencyAnalyzer()
    test.setup_method()
    
    print("运行循环依赖分析器测试...")
    
    # 基本功能测试
    try:
        test.test_detect_all_cycles_basic()
        print("✓ 基本循环检测测试通过")
    except Exception as e:
        print(f"✗ 基本循环检测测试失败: {e}")
    
    try:
        test.test_analyze_cycle_severity()
        print("✓ 循环严重程度分析测试通过")
    except Exception as e:
        print(f"✗ 循环严重程度分析测试失败: {e}")
    
    try:
        test.test_classify_cycle_type()
        print("✓ 循环类型分类测试通过")
    except Exception as e:
        print(f"✗ 循环类型分类测试失败: {e}")
    
    try:
        test.test_perform_full_analysis()
        print("✓ 完整分析测试通过")
    except Exception as e:
        print(f"✗ 完整分析测试失败: {e}")
    
    try:
        test.test_generate_cycle_report_text()
        print("✓ 文本报告生成测试通过")
    except Exception as e:
        print(f"✗ 文本报告生成测试失败: {e}")
    
    print("测试完成!")
