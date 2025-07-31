"""Unity Resource Reference Scanner - Circular Dependency Analysis Module

环形依赖检测和分析增强模块，基于现有的find_circular_dependencies()方法，
实现完整的环形依赖检测和分析系统。提供详细的循环路径信息、循环类型分析、
解决建议等功能。
"""

from typing import Dict, List, Set, Optional, Any, Tuple, Union, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import logging
from collections import defaultdict

import networkx as nx

# 前向引用依赖图类
if TYPE_CHECKING:
    from .dependency_graph import DependencyGraph


class CycleType(Enum):
    """循环依赖类型"""
    SELF_LOOP = "self_loop"          # 自循环
    SIMPLE_CYCLE = "simple_cycle"    # 简单循环
    COMPLEX_CYCLE = "complex_cycle"  # 复杂循环
    NESTED_CYCLE = "nested_cycle"    # 嵌套循环
    
    @property
    def display_name(self) -> str:
        """获取显示名称"""
        return self.value


class CycleSeverity(Enum):
    """循环依赖严重程度"""
    LOW = 1          # 低风险
    MEDIUM = 2       # 中等风险  
    HIGH = 3         # 高风险
    CRITICAL = 4     # 严重风险
    
    def __lt__(self, other):
        if isinstance(other, CycleSeverity):
            return self.value < other.value
        return NotImplemented
    
    def __le__(self, other):
        if isinstance(other, CycleSeverity):
            return self.value <= other.value
        return NotImplemented
    
    def __gt__(self, other):
        if isinstance(other, CycleSeverity):
            return self.value > other.value
        return NotImplemented
    
    def __ge__(self, other):
        if isinstance(other, CycleSeverity):
            return self.value >= other.value
        return NotImplemented
    
    @property
    def display_name(self) -> str:
        """获取显示名称"""
        names = {
            CycleSeverity.LOW: "low",
            CycleSeverity.MEDIUM: "medium",
            CycleSeverity.HIGH: "high",
            CycleSeverity.CRITICAL: "critical"
        }
        return names[self]


@dataclass
class CycleInfo:
    """循环依赖信息"""
    cycle_id: str
    nodes: List[str]
    edges: List[Tuple[str, str]]
    cycle_type: CycleType
    severity: CycleSeverity
    length: int
    detected_at: datetime
    
    # 分析信息
    critical_nodes: List[str]      # 关键节点
    breakable_edges: List[Tuple[str, str]]  # 可断开的边
    suggested_fixes: List[str]     # 修复建议
    
    # 统计信息
    node_types: Dict[str, int]     # 节点类型统计
    edge_strengths: Dict[str, int] # 边强度统计
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'cycle_id': self.cycle_id,
            'nodes': self.nodes,
            'edges': [(src, tgt) for src, tgt in self.edges],
            'cycle_type': self.cycle_type.display_name,
            'severity': self.severity.display_name,
            'length': self.length,
            'detected_at': self.detected_at.isoformat(),
            'critical_nodes': self.critical_nodes,
            'breakable_edges': [(src, tgt) for src, tgt in self.breakable_edges],
            'suggested_fixes': self.suggested_fixes,
            'node_types': self.node_types,
            'edge_strengths': self.edge_strengths
        }


@dataclass
class CycleAnalysisReport:
    """循环依赖分析报告"""
    total_cycles: int
    cycle_distribution: Dict[CycleType, int]
    severity_distribution: Dict[CycleSeverity, int]
    cycles: List[CycleInfo]
    
    # 全局统计
    affected_nodes: Set[str]
    hotspot_nodes: List[Tuple[str, int]]  # 出现在多个循环中的节点
    largest_cycle: Optional[CycleInfo]
    most_critical_cycle: Optional[CycleInfo]
    
    # 性能统计
    analysis_time_seconds: float
    detection_algorithm: str
    
    analyzed_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'total_cycles': self.total_cycles,
            'cycle_distribution': {k.display_name: v for k, v in self.cycle_distribution.items()},
            'severity_distribution': {k.display_name: v for k, v in self.severity_distribution.items()},
            'cycles': [cycle.to_dict() for cycle in self.cycles],
            'affected_nodes': list(self.affected_nodes),
            'hotspot_nodes': self.hotspot_nodes,
            'largest_cycle': self.largest_cycle.to_dict() if self.largest_cycle else None,
            'most_critical_cycle': self.most_critical_cycle.to_dict() if self.most_critical_cycle else None,
            'analysis_time_seconds': self.analysis_time_seconds,
            'detection_algorithm': self.detection_algorithm,
            'analyzed_at': self.analyzed_at.isoformat()
        }


class CircularDependencyAnalyzer:
    """环形依赖检测和分析器
    
    基于现有的find_circular_dependencies()方法，实现完整的环形依赖检测和分析系统
    """
    
    def __init__(self, graph: 'DependencyGraph'):
        """初始化分析器
        
        Args:
            graph: 依赖关系图
        """
        self.graph = graph
        self.logger = logging.getLogger(__name__)
        
        # 分析配置
        self.severity_thresholds = {
            'critical_length': 10,      # 循环长度超过10认为严重
            'high_length': 6,           # 循环长度超过6认为高风险
            'medium_length': 3          # 循环长度超过3认为中等风险
        }
        
        # 缓存
        self._last_analysis: Optional[CycleAnalysisReport] = None
        self._analysis_cache_timestamp: Optional[datetime] = None
    
    def detect_all_cycles(self, use_enhanced_detection: bool = True) -> List[List[str]]:
        """检测图中所有循环依赖
        
        Args:
            use_enhanced_detection: 是否使用增强检测算法
            
        Returns:
            List[List[str]]: 所有循环依赖路径列表
        """
        self.logger.info("开始检测所有循环依赖")
        
        if use_enhanced_detection:
            return self._detect_cycles_enhanced()
        else:
            # 使用原有方法
            return self.graph.find_circular_dependencies()
    
    def _detect_cycles_enhanced(self) -> List[List[str]]:
        """增强的循环检测算法"""
        cycles = []
        
        if not isinstance(self.graph.graph, nx.DiGraph):
            return cycles
        
        try:
            # 1. 首先使用强连通分量算法
            sccs = list(nx.strongly_connected_components(self.graph.graph))
            
            for scc in sccs:
                if len(scc) > 1:
                    # 对于复杂的强连通分量，找出所有简单循环
                    subgraph = self.graph.graph.subgraph(scc)
                    cycles.extend(self._find_all_simple_cycles_in_scc(subgraph))
                elif len(scc) == 1:
                    # 检查自循环
                    node = list(scc)[0]
                    if self.graph.has_edge(node, node):
                        cycles.append([node, node])
            
            # 2. 使用Johnson算法查找所有简单循环（限制长度避免性能问题）
            try:
                johnson_cycles = list(nx.simple_cycles(self.graph.graph))
                # 限制循环长度，避免过长的循环
                filtered_cycles = [cycle for cycle in johnson_cycles if len(cycle) <= 20]
                cycles.extend(filtered_cycles)
            except Exception as e:
                self.logger.warning(f"Johnson算法执行失败: {e}")
            
            # 3. 去重
            cycles = self._deduplicate_cycles(cycles)
            
        except Exception as e:
            self.logger.error(f"增强循环检测失败: {e}")
            # 回退到原始方法
            cycles = self.graph.find_circular_dependencies()
        
        self.logger.info(f"检测到 {len(cycles)} 个循环依赖")
        return cycles
    
    def _find_all_simple_cycles_in_scc(self, subgraph: nx.DiGraph) -> List[List[str]]:
        """在强连通分量中查找所有简单循环"""
        cycles = []
        
        try:
            # 使用DFS查找简单循环
            visited = set()
            
            for start_node in subgraph.nodes():
                if start_node not in visited:
                    stack = [(start_node, [start_node])]
                    path_set = {start_node}
                    
                    while stack:
                        node, path = stack.pop()
                        
                        for neighbor in subgraph.successors(node):
                            if neighbor == start_node and len(path) > 1:
                                # 找到回到起始节点的循环
                                cycle = path + [start_node]
                                cycles.append(cycle)
                            elif neighbor not in path_set and len(path) < 10:  # 限制路径长度
                                stack.append((neighbor, path + [neighbor]))
                                path_set.add(neighbor)
                
                visited.add(start_node)
        
        except Exception as e:
            self.logger.warning(f"SCC内循环检测失败: {e}")
        
        return cycles
    
    def _deduplicate_cycles(self, cycles: List[List[str]]) -> List[List[str]]:
        """去重循环"""
        unique_cycles = []
        seen_cycles = set()
        
        for cycle in cycles:
            if len(cycle) < 2:
                continue
            
            # 标准化循环表示（从最小节点开始）
            if cycle[0] == cycle[-1]:
                # 如果首尾相同，移除最后一个
                cycle = cycle[:-1]
            
            if not cycle:
                continue
            
            # 找到最小节点的位置
            min_idx = cycle.index(min(cycle))
            normalized = cycle[min_idx:] + cycle[:min_idx]
            
            # 检查是否已存在（考虑反向）
            normalized_tuple = tuple(normalized)
            reversed_tuple = tuple(normalized[::-1])
            
            if normalized_tuple not in seen_cycles and reversed_tuple not in seen_cycles:
                seen_cycles.add(normalized_tuple)
                unique_cycles.append(normalized + [normalized[0]])  # 添加首尾相同形式
        
        return unique_cycles
    
    def analyze_cycle_severity(self, cycle: List[str]) -> CycleSeverity:
        """分析循环依赖的严重程度
        
        Args:
            cycle: 循环路径
            
        Returns:
            CycleSeverity: 严重程度
        """
        if len(cycle) <= 1:
            return CycleSeverity.LOW
        
        # 基于循环长度的基础评估
        cycle_length = len(cycle) - 1  # 减去重复的首尾节点
        
        if cycle_length >= self.severity_thresholds['critical_length']:
            base_severity = CycleSeverity.CRITICAL
        elif cycle_length >= self.severity_thresholds['high_length']:
            base_severity = CycleSeverity.HIGH
        elif cycle_length >= self.severity_thresholds['medium_length']:
            base_severity = CycleSeverity.MEDIUM
        else:
            base_severity = CycleSeverity.LOW
        
        # 基于边强度的修正
        severity_score = self._calculate_severity_score(cycle)
        
        # 根据综合评分调整严重程度
        if severity_score >= 0.8:
            return CycleSeverity.CRITICAL
        elif severity_score >= 0.6:
            return max(base_severity, CycleSeverity.HIGH)
        elif severity_score >= 0.4:
            return max(base_severity, CycleSeverity.MEDIUM)
        else:
            return base_severity
    
    def _calculate_severity_score(self, cycle: List[str]) -> float:
        """计算循环的严重程度评分"""
        if len(cycle) <= 1:
            return 0.0
        
        score_factors = []
        
        # 1. 边强度因子
        strong_edges = 0
        total_edges = 0
        
        for i in range(len(cycle) - 1):
            source = cycle[i]
            target = cycle[i + 1]
            edge_data = self.graph.get_edge_data(source, target)
            
            if edge_data:
                total_edges += 1
                strength = edge_data.get('dependency_strength', 'weak')
                if strength in ['critical', 'important']:
                    strong_edges += 1
        
        if total_edges > 0:
            strength_factor = strong_edges / total_edges
            score_factors.append(strength_factor)
        
        # 2. 节点类型因子
        critical_nodes = 0
        total_nodes = len(set(cycle[:-1]))  # 去重并排除重复的首尾节点
        
        for node in set(cycle[:-1]):
            node_data = self.graph.get_node_data(node)
            if node_data:
                asset_type = node_data.get('asset_type', '')
                if asset_type in ['scene', 'prefab', 'script']:
                    critical_nodes += 1
        
        if total_nodes > 0:
            type_factor = critical_nodes / total_nodes
            score_factors.append(type_factor)
        
        # 3. 循环复杂度因子
        complexity_factor = min(1.0, (len(cycle) - 1) / 10.0)
        score_factors.append(complexity_factor)
        
        # 计算综合评分
        if score_factors:
            return sum(score_factors) / len(score_factors)
        else:
            return 0.0
    
    def classify_cycle_type(self, cycle: List[str]) -> CycleType:
        """分类循环依赖类型
        
        Args:
            cycle: 循环路径
            
        Returns:
            CycleType: 循环类型
        """
        if len(cycle) <= 1:
            return CycleType.SELF_LOOP
        
        cycle_length = len(cycle) - 1  # 减去重复的首尾节点
        
        if cycle_length == 1:
            return CycleType.SELF_LOOP
        elif cycle_length <= 3:
            return CycleType.SIMPLE_CYCLE
        elif cycle_length <= 8:
            return CycleType.COMPLEX_CYCLE
        else:
            return CycleType.NESTED_CYCLE
    
    def find_critical_nodes(self, cycle: List[str]) -> List[str]:
        """找到循环中的关键节点
        
        Args:
            cycle: 循环路径
            
        Returns:
            List[str]: 关键节点列表
        """
        if len(cycle) <= 2:
            return cycle[:-1] if cycle else []
        
        critical_nodes = []
        unique_nodes = list(set(cycle[:-1]))
        
        for node in unique_nodes:
            # 计算节点的度数（在循环内）
            in_degree = sum(1 for i in range(len(cycle) - 1) if cycle[i + 1] == node)
            out_degree = sum(1 for i in range(len(cycle) - 1) if cycle[i] == node)
            
            # 检查节点类型
            node_data = self.graph.get_node_data(node)
            is_critical_type = False
            if node_data:
                asset_type = node_data.get('asset_type', '')
                is_critical_type = asset_type in ['scene', 'prefab', 'script']
            
            # 关键节点判断条件
            if (in_degree > 1 or out_degree > 1 or is_critical_type):
                critical_nodes.append(node)
        
        return critical_nodes
    
    def suggest_cycle_fixes(self, cycle: List[str]) -> List[str]:
        """为循环依赖提供修复建议
        
        Args:
            cycle: 循环路径
            
        Returns:
            List[str]: 修复建议列表
        """
        suggestions = []
        
        if len(cycle) <= 2:
            suggestions.append("移除自循环依赖")
            return suggestions
        
        # 1. 找到可断开的边
        breakable_edges = self.find_breakable_edges(cycle)
        if breakable_edges:
            for source, target in breakable_edges:
                suggestions.append(f"考虑断开边: {source} -> {target}")
        
        # 2. 架构重构建议
        cycle_length = len(cycle) - 1
        if cycle_length > 5:
            suggestions.append("考虑引入中介模式或观察者模式来解耦组件")
        
        # 3. 依赖注入建议
        if any(self._is_script_node(node) for node in cycle[:-1]):
            suggestions.append("考虑使用依赖注入或服务定位器模式")
        
        # 4. 接口分离建议
        suggestions.append("考虑使用接口分离原则，提取公共接口")
        
        # 5. 延迟初始化建议
        suggestions.append("考虑使用延迟初始化或懒加载模式")
        
        return suggestions
    
    def find_breakable_edges(self, cycle: List[str]) -> List[Tuple[str, str]]:
        """找到循环中可以断开的边
        
        Args:
            cycle: 循环路径
            
        Returns:
            List[Tuple[str, str]]: 可断开的边列表
        """
        breakable_edges = []
        
        for i in range(len(cycle) - 1):
            source = cycle[i]
            target = cycle[i + 1]
            edge_data = self.graph.get_edge_data(source, target)
            
            if edge_data:
                strength = edge_data.get('dependency_strength', 'weak')
                dep_type = edge_data.get('dependency_type', 'unknown')
                
                # 优先考虑弱依赖和某些类型的依赖
                if (strength in ['weak', 'optional'] or 
                    dep_type in ['reference', 'asset_reference']):
                    breakable_edges.append((source, target))
        
        return breakable_edges
    
    def _is_script_node(self, node: str) -> bool:
        """检查节点是否为脚本类型"""
        node_data = self.graph.get_node_data(node)
        if node_data:
            asset_type = node_data.get('asset_type', '')
            return asset_type == 'script'
        return False
    
    def perform_full_analysis(self) -> CycleAnalysisReport:
        """执行完整的循环依赖分析
        
        Returns:
            CycleAnalysisReport: 完整的分析报告
        """
        start_time = datetime.utcnow()
        self.logger.info("开始执行完整的循环依赖分析")
        
        # 检测所有循环
        cycles_raw = self.detect_all_cycles(use_enhanced_detection=True)
        
        # 分析每个循环
        cycles_info = []
        cycle_distribution = defaultdict(int)
        severity_distribution = defaultdict(int)
        affected_nodes = set()
        node_cycle_count = defaultdict(int)
        
        for i, cycle in enumerate(cycles_raw):
            cycle_id = f"cycle_{i:04d}"
            
            # 基本信息
            cycle_type = self.classify_cycle_type(cycle)
            severity = self.analyze_cycle_severity(cycle)
            
            # 详细分析
            critical_nodes = self.find_critical_nodes(cycle)
            breakable_edges = self.find_breakable_edges(cycle)
            suggestions = self.suggest_cycle_fixes(cycle)
            
            # 构建边列表
            edges = []
            for j in range(len(cycle) - 1):
                edges.append((cycle[j], cycle[j + 1]))
            
            # 统计信息
            node_types = self._analyze_node_types(cycle)
            edge_strengths = self._analyze_edge_strengths(cycle)
            
            cycle_info = CycleInfo(
                cycle_id=cycle_id,
                nodes=cycle,
                edges=edges,
                cycle_type=cycle_type,
                severity=severity,
                length=len(cycle) - 1,
                detected_at=datetime.utcnow(),
                critical_nodes=critical_nodes,
                breakable_edges=breakable_edges,
                suggested_fixes=suggestions,
                node_types=node_types,
                edge_strengths=edge_strengths
            )
            
            cycles_info.append(cycle_info)
            
            # 更新统计
            cycle_distribution[cycle_type] += 1
            severity_distribution[severity] += 1
            
            # 更新受影响的节点
            unique_nodes = set(cycle[:-1]) if cycle else set()
            affected_nodes.update(unique_nodes)
            
            # 统计节点出现频率
            for node in unique_nodes:
                node_cycle_count[node] += 1
        
        # 找到热点节点
        hotspot_nodes = sorted(node_cycle_count.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # 找到最大和最严重的循环
        largest_cycle = max(cycles_info, key=lambda x: x.length) if cycles_info else None
        most_critical_cycle = None
        
        if cycles_info:
            # 按严重程度排序
            most_critical_cycle = max(cycles_info, 
                                    key=lambda x: (x.severity, x.length))
        
        # 计算分析时间
        analysis_time = (datetime.utcnow() - start_time).total_seconds()
        
        report = CycleAnalysisReport(
            total_cycles=len(cycles_info),
            cycle_distribution=dict(cycle_distribution),
            severity_distribution=dict(severity_distribution),
            cycles=cycles_info,
            affected_nodes=affected_nodes,
            hotspot_nodes=hotspot_nodes,
            largest_cycle=largest_cycle,
            most_critical_cycle=most_critical_cycle,
            analysis_time_seconds=analysis_time,
            detection_algorithm="enhanced_scc_johnson",
            analyzed_at=datetime.utcnow()
        )
        
        # 缓存结果
        self._last_analysis = report
        self._analysis_cache_timestamp = datetime.utcnow()
        
        self.logger.info(f"循环依赖分析完成，发现 {report.total_cycles} 个循环，耗时 {analysis_time:.2f} 秒")
        
        return report
    
    def _analyze_node_types(self, cycle: List[str]) -> Dict[str, int]:
        """分析循环中节点类型分布"""
        type_count = defaultdict(int)
        
        for node in set(cycle[:-1]) if cycle else []:
            node_data = self.graph.get_node_data(node)
            if node_data:
                asset_type = node_data.get('asset_type', 'unknown')
                type_count[asset_type] += 1
            else:
                type_count['unknown'] += 1
        
        return dict(type_count)
    
    def _analyze_edge_strengths(self, cycle: List[str]) -> Dict[str, int]:
        """分析循环中边强度分布"""
        strength_count = defaultdict(int)
        
        for i in range(len(cycle) - 1):
            source = cycle[i]
            target = cycle[i + 1]
            edge_data = self.graph.get_edge_data(source, target)
            
            if edge_data:
                strength = edge_data.get('dependency_strength', 'unknown')
                strength_count[strength] += 1
            else:
                strength_count['unknown'] += 1
        
        return dict(strength_count)
    
    def get_incremental_analysis(self, 
                                changed_nodes: Set[str],
                                changed_edges: Set[Tuple[str, str]]) -> CycleAnalysisReport:
        """增量循环依赖分析
        
        Args:
            changed_nodes: 变更的节点集合
            changed_edges: 变更的边集合
            
        Returns:
            CycleAnalysisReport: 增量分析报告
        """
        self.logger.info(f"执行增量循环依赖分析: {len(changed_nodes)} 节点, {len(changed_edges)} 边")
        
        # 如果变更较大，直接执行完整分析
        total_nodes = self.graph.get_node_count()
        total_edges = self.graph.get_edge_count()
        
        if (len(changed_nodes) > total_nodes * 0.1 or 
            len(changed_edges) > total_edges * 0.1):
            self.logger.info("变更范围较大，执行完整分析")
            return self.perform_full_analysis()
        
        # 构建影响范围子图
        affected_nodes = set(changed_nodes)
        
        # 扩展到相邻节点
        for node in changed_nodes:
            affected_nodes.update(self.graph.get_predecessors(node))
            affected_nodes.update(self.graph.get_successors(node))
        
        for source, target in changed_edges:
            affected_nodes.add(source)
            affected_nodes.add(target)
        
        # 在子图中检测循环
        subgraph = self.graph.graph.subgraph(affected_nodes)
        
        # 执行局部循环检测
        cycles_raw = self._detect_cycles_in_subgraph(subgraph)
        
        # 生成简化的分析报告
        return self._generate_incremental_report(cycles_raw, affected_nodes)
    
    def _detect_cycles_in_subgraph(self, subgraph: nx.DiGraph) -> List[List[str]]:
        """在子图中检测循环"""
        cycles = []
        
        try:
            # 使用Johnson算法在子图中查找循环
            johnson_cycles = list(nx.simple_cycles(subgraph))
            cycles.extend(johnson_cycles)
            
            # 检查自循环
            for node in subgraph.nodes():
                if subgraph.has_edge(node, node):
                    cycles.append([node, node])
                    
        except Exception as e:
            self.logger.warning(f"子图循环检测失败: {e}")
        
        return self._deduplicate_cycles(cycles)
    
    def _generate_incremental_report(self, 
                                   cycles_raw: List[List[str]], 
                                   affected_nodes: Set[str]) -> CycleAnalysisReport:
        """生成增量分析报告"""
        start_time = datetime.utcnow()
        
        # 简化的循环分析
        cycles_info = []
        cycle_distribution = defaultdict(int)
        severity_distribution = defaultdict(int)
        
        for i, cycle in enumerate(cycles_raw):
            cycle_id = f"incremental_cycle_{i:04d}"
            cycle_type = self.classify_cycle_type(cycle)
            severity = self.analyze_cycle_severity(cycle)
            
            # 基本信息
            edges = [(cycle[j], cycle[j + 1]) for j in range(len(cycle) - 1)]
            
            cycle_info = CycleInfo(
                cycle_id=cycle_id,
                nodes=cycle,
                edges=edges,
                cycle_type=cycle_type,
                severity=severity,
                length=len(cycle) - 1,
                detected_at=datetime.utcnow(),
                critical_nodes=self.find_critical_nodes(cycle),
                breakable_edges=self.find_breakable_edges(cycle),
                suggested_fixes=self.suggest_cycle_fixes(cycle),
                node_types=self._analyze_node_types(cycle),
                edge_strengths=self._analyze_edge_strengths(cycle)
            )
            
            cycles_info.append(cycle_info)
            cycle_distribution[cycle_type] += 1
            severity_distribution[severity] += 1
        
        analysis_time = (datetime.utcnow() - start_time).total_seconds()
        
        return CycleAnalysisReport(
            total_cycles=len(cycles_info),
            cycle_distribution=dict(cycle_distribution),
            severity_distribution=dict(severity_distribution),
            cycles=cycles_info,
            affected_nodes=affected_nodes,
            hotspot_nodes=[],  # 增量分析不计算热点
            largest_cycle=max(cycles_info, key=lambda x: x.length) if cycles_info else None,
            most_critical_cycle=max(cycles_info, key=lambda x: x.severity) if cycles_info else None,
            analysis_time_seconds=analysis_time,
            detection_algorithm="incremental_johnson",
            analyzed_at=datetime.utcnow()
        )
    
    def generate_cycle_report(self, 
                            report: CycleAnalysisReport, 
                            format_type: str = "text") -> str:
        """生成循环依赖报告
        
        Args:
            report: 分析报告
            format_type: 报告格式 ("text", "markdown", "json")
            
        Returns:
            str: 格式化的报告内容
        """
        if format_type == "json":
            import json
            return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
        elif format_type == "markdown":
            return self._generate_markdown_report(report)
        else:
            return self._generate_text_report(report)
    
    def _generate_text_report(self, report: CycleAnalysisReport) -> str:
        """生成文本格式报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("循环依赖分析报告")
        lines.append("=" * 60)
        lines.append(f"分析时间: {report.analyzed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"检测算法: {report.detection_algorithm}")
        lines.append(f"分析耗时: {report.analysis_time_seconds:.2f} 秒")
        lines.append("")
        
        # 统计摘要
        lines.append("统计摘要:")
        lines.append(f"  总循环数: {report.total_cycles}")
        lines.append(f"  受影响节点: {len(report.affected_nodes)}")
        lines.append("")
        
        # 循环类型分布
        lines.append("循环类型分布:")
        for cycle_type, count in report.cycle_distribution.items():
            lines.append(f"  {cycle_type}: {count}")
        lines.append("")
        
        # 严重程度分布
        lines.append("严重程度分布:")
        for severity, count in report.severity_distribution.items():
            lines.append(f"  {severity}: {count}")
        lines.append("")
        
        # 热点节点
        if report.hotspot_nodes:
            lines.append("热点节点 (出现在多个循环中):")
            for node, count in report.hotspot_nodes[:5]:
                lines.append(f"  {node}: {count} 个循环")
            lines.append("")
        
        # 最大循环
        if report.largest_cycle:
            lines.append(f"最大循环: {report.largest_cycle.cycle_id}")
            lines.append(f"  长度: {report.largest_cycle.length}")
            lines.append(f"  节点: {' -> '.join(report.largest_cycle.nodes)}")
            lines.append("")
        
        # 最严重循环
        if report.most_critical_cycle:
            lines.append(f"最严重循环: {report.most_critical_cycle.cycle_id}")
            lines.append(f"  严重程度: {report.most_critical_cycle.severity.display_name}")
            lines.append(f"  建议修复:")
            for suggestion in report.most_critical_cycle.suggested_fixes:
                lines.append(f"    - {suggestion}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_markdown_report(self, report: CycleAnalysisReport) -> str:
        """生成Markdown格式报告"""
        lines = []
        lines.append("# 循环依赖分析报告")
        lines.append("")
        lines.append(f"**分析时间**: {report.analyzed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**检测算法**: {report.detection_algorithm}")
        lines.append(f"**分析耗时**: {report.analysis_time_seconds:.2f} 秒")
        lines.append("")
        
        # 统计摘要
        lines.append("## 统计摘要")
        lines.append("")
        lines.append(f"- **总循环数**: {report.total_cycles}")
        lines.append(f"- **受影响节点**: {len(report.affected_nodes)}")
        lines.append("")
        
        # 循环类型分布
        lines.append("## 循环类型分布")
        lines.append("")
        for cycle_type, count in report.cycle_distribution.items():
            lines.append(f"- **{cycle_type}**: {count}")
        lines.append("")
        
        # 严重程度分布
        lines.append("## 严重程度分布")
        lines.append("")
        for severity, count in report.severity_distribution.items():
            lines.append(f"- **{severity}**: {count}")
        lines.append("")
        
        # 热点节点
        if report.hotspot_nodes:
            lines.append("## 热点节点")
            lines.append("")
            lines.append("| 节点 | 循环数量 |")
            lines.append("|------|----------|")
            for node, count in report.hotspot_nodes[:10]:
                lines.append(f"| {node} | {count} |")
            lines.append("")
        
        # 详细循环信息
        if report.cycles and len(report.cycles) <= 20:  # 只显示前20个循环
            lines.append("## 详细循环信息")
            lines.append("")
            
            for cycle in report.cycles[:20]:
                lines.append(f"### {cycle.cycle_id}")
                lines.append("")
                lines.append(f"- **类型**: {cycle.cycle_type.display_name}")
                lines.append(f"- **严重程度**: {cycle.severity.display_name}")
                lines.append(f"- **长度**: {cycle.length}")
                lines.append(f"- **路径**: {' → '.join(cycle.nodes)}")
                
                if cycle.suggested_fixes:
                    lines.append("- **修复建议**:")
                    for suggestion in cycle.suggested_fixes:
                        lines.append(f"  - {suggestion}")
                lines.append("")
        
        return "\n".join(lines)
