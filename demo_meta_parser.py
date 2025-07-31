#!/usr/bin/env python3
"""Meta文件解析器演示脚本

展示Unity Meta文件解析器的主要功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.meta_parser import MetaParser, ImporterType
from src.parsers.base_parser import ParseResultType


def demo_meta_parser():
    """演示Meta解析器功能"""
    print("🎯 Unity Meta文件解析器演示")
    print("=" * 50)
    
    # 创建解析器实例
    parser = MetaParser()
    
    # 1. 显示解析器信息
    print("\n📊 解析器信息:")
    stats = parser.get_parser_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 2. 查找fixture文件
    fixtures_path = project_root / "tests" / "fixtures"
    if not fixtures_path.exists():
        print(f"\n❌ Fixtures目录不存在: {fixtures_path}")
        return
    
    meta_files = list(fixtures_path.glob("*.meta"))
    if not meta_files:
        print(f"\n❌ 没有找到Meta文件")
        return
    
    print(f"\n📁 找到 {len(meta_files)} 个Meta文件:")
    for meta_file in meta_files:
        print(f"  - {meta_file.name}")
    
    # 3. 逐个解析文件
    print(f"\n🔍 解析结果:")
    success_count = 0
    failed_count = 0
    
    for meta_file in meta_files:
        print(f"\n  📄 {meta_file.name}:")
        
        result = parser.parse(meta_file)
        
        if result.is_success:
            success_count += 1
            print(f"    ✅ 解析成功")
            print(f"    🆔 GUID: {result.guid}")
            print(f"    📦 资源类型: {result.asset_type}")
            
            if result.data:
                importer_type = result.data.get('importer_type', 'unknown')
                file_format_version = result.data.get('file_format_version', 'unknown')
                print(f"    🔧 导入器: {importer_type}")
                print(f"    📋 格式版本: {file_format_version}")
                
                # 显示用户数据（如果有）
                user_data = result.data.get('user_data')
                if user_data:
                    print(f"    👤 用户数据: {user_data}")
                
                # 显示资源包信息（如果有）
                bundle_name = result.data.get('asset_bundle_name')
                if bundle_name:
                    print(f"    📦 资源包: {bundle_name}")
            
            # 显示警告（如果有）
            if result.warnings:
                print(f"    ⚠️  警告 ({len(result.warnings)}个):")
                for warning in result.warnings:
                    print(f"       - {warning}")
                    
        elif result.is_failed:
            failed_count += 1
            print(f"    ❌ 解析失败: {result.error_message}")
            
        else:
            print(f"    ⏭️  跳过: {result.error_message}")
    
    # 4. 显示统计结果
    print(f"\n📈 解析统计:")
    print(f"  成功: {success_count}")
    print(f"  失败: {failed_count}")
    print(f"  总计: {len(meta_files)}")
    print(f"  成功率: {success_count / len(meta_files) * 100:.1f}%")
    
    # 5. 演示快速GUID提取
    print(f"\n⚡ 快速GUID提取演示:")
    for meta_file in meta_files:
        guid = parser.extract_guid_only(meta_file)
        if guid:
            print(f"  {meta_file.name}: {guid}")
        else:
            print(f"  {meta_file.name}: 提取失败")
    
    # 6. 演示批量解析
    print(f"\n🔄 批量解析演示:")
    batch_results = parser.parse_batch(meta_files)
    batch_success = sum(1 for r in batch_results if r.is_success)
    print(f"  批量解析结果: {batch_success}/{len(batch_results)} 成功")
    
    # 7. 显示支持的导入器类型
    print(f"\n🔧 支持的导入器类型 ({len(ImporterType)} 种):")
    for importer_type in ImporterType:
        if importer_type != ImporterType.UNKNOWN:
            print(f"  - {importer_type.value}")
    
    print(f"\n🎉 演示完成！")


def demo_specific_file(file_path: str):
    """演示解析特定文件"""
    print(f"🎯 解析特定Meta文件: {file_path}")
    print("=" * 50)
    
    meta_path = Path(file_path)
    if not meta_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return
    
    parser = MetaParser()
    
    # 检查是否可以解析
    if not parser.can_parse(meta_path):
        print(f"❌ 无法解析此文件")
        return
    
    # 解析文件
    result = parser.parse(meta_path)
    
    if result.is_success:
        print(f"✅ 解析成功")
        print(f"🆔 GUID: {result.guid}")
        print(f"📦 资源类型: {result.asset_type}")
        print(f"📄 文件路径: {result.file_path}")
        
        if result.data:
            print(f"\n📋 详细信息:")
            for key, value in result.data.items():
                if key != 'importer_data':  # 跳过复杂的导入器数据
                    print(f"  {key}: {value}")
        
        if result.warnings:
            print(f"\n⚠️  警告:")
            for warning in result.warnings:
                print(f"  - {warning}")
                
    else:
        print(f"❌ 解析失败: {result.error_message}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 解析指定文件
        demo_specific_file(sys.argv[1])
    else:
        # 运行完整演示
        demo_meta_parser()
