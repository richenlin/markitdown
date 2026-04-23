#!/usr/bin/env python3
"""
Knowledge Trigger Detector

知识触发检测器 - 根据用户输入和项目上下文自动检测并加载相关知识。

触发方式：
1. 项目检测 (package.json, go.mod, pom.xml 等)
2. 用户输入关键字匹配
3. 场景推断 (根据动词和上下文)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Import query functions
from query import (
    get_kb_root, load_json, get_global_index,
    query_by_triggers, query_by_category, get_entry,
    query_semantic, query_hybrid,
)


# 场景关键字映射
SCENARIO_KEYWORDS = {
    'api': ['api', 'rest', 'restful', 'graphql', 'endpoint', '接口', '请求'],
    'auth': ['auth', 'login', 'logout', '登录', '认证', '授权', 'jwt', 'oauth', 'session'],
    'database': ['database', 'db', 'sql', 'query', '数据库', 'mysql', 'postgres', 'mongodb', 'redis'],
    'testing': ['test', 'testing', 'unit', 'e2e', 'integration', '测试', 'jest', 'pytest', 'vitest'],
    'deploy': ['deploy', 'deployment', 'ci', 'cd', 'docker', 'k8s', '部署', '上线'],
    'performance': ['performance', 'optimize', 'slow', 'fast', '性能', '优化', '慢'],
    'security': ['security', 'secure', 'xss', 'csrf', 'injection', '安全', '漏洞'],
    'state': ['state', 'store', 'redux', 'vuex', 'zustand', '状态管理'],
    'form': ['form', 'validation', 'input', '表单', '校验'],
    'routing': ['route', 'router', 'navigation', '路由', '导航'],
    'error': ['error', 'bug', 'fix', 'debug', '错误', '报错', 'issue', '问题']
}

# 问题症状关键字
PROBLEM_SYMPTOMS = {
    'cors': ['cors', '跨域', 'cross-origin', 'access-control'],
    'memory': ['memory', 'leak', '内存', '泄露', 'oom'],
    'timeout': ['timeout', '超时', 'hang', '卡住'],
    'crash': ['crash', '崩溃', '闪退'],
    'import': ['import', 'module', 'cannot find', '找不到模块', 'not found'],
    'type': ['type', 'typescript', '类型错误', 'type error'],
    'null': ['null', 'undefined', 'cannot read', 'is not defined'],
    'async': ['async', 'await', 'promise', 'callback', '异步']
}

# 动作关键字映射到场景
ACTION_TO_SCENARIO = {
    'create': 'scenario', 'build': 'scenario', 'implement': 'scenario', 'add': 'scenario',
    '创建': 'scenario', '实现': 'scenario', '开发': 'scenario', '新增': 'scenario',
    'fix': 'problem', 'debug': 'problem', 'solve': 'problem', 'resolve': 'problem',
    '修复': 'problem', '解决': 'problem', '排查': 'problem',
    'optimize': 'experience', 'improve': 'experience', 'refactor': 'experience',
    '优化': 'experience', '重构': 'experience',
    'test': 'testing', 'mock': 'testing', '测试': 'testing', '验证': 'testing'
}


def extract_keywords(text: str) -> List[str]:
    """从文本中提取关键字。"""
    keywords: Set[str] = set()
    
    # 英文单词 (3+ 字符)
    english_words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9\-\.]+\b', text.lower())
    keywords.update(w for w in english_words if len(w) >= 3)
    
    # 中文词组 (2-4字)
    chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
    keywords.update(chinese_words)
    
    # 技术术语 (如 react-query, vue.js)
    tech_terms = re.findall(r'[a-zA-Z]+[\-\.][a-zA-Z]+', text.lower())
    keywords.update(tech_terms)
    
    return list(keywords)


def detect_scenarios(text: str) -> List[str]:
    """检测文本中涉及的场景。"""
    text_lower = text.lower()
    detected: Set[str] = set()
    
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                detected.add(scenario)
                break
    
    return list(detected)


def detect_problems(text: str) -> List[str]:
    """检测文本中描述的问题类型。"""
    text_lower = text.lower()
    detected: Set[str] = set()
    
    for problem, symptoms in PROBLEM_SYMPTOMS.items():
        for symptom in symptoms:
            if symptom in text_lower:
                detected.add(problem)
                break
    
    return list(detected)


def detect_action_type(text: str) -> Optional[str]:
    """检测用户意图的动作类型。"""
    text_lower = text.lower()
    
    for action, category in ACTION_TO_SCENARIO.items():
        if action in text_lower:
            return category
    
    return None


def detect_project_tech(project_dir: str) -> Dict[str, Any]:
    """检测项目技术栈。"""
    detector_path = Path(__file__).parent.parent / 'programming'
    sys.path.insert(0, str(detector_path))
    
    try:
        from detect_project import detect_project
        return detect_project(project_dir)
    except ImportError:
        return {'error': 'Project detector not available'}


def trigger_knowledge(
    user_input: Optional[str] = None,
    project_dir: Optional[str] = None,
    explicit_triggers: Optional[List[str]] = None,
    limit: int = 5,
    mode: str = 'hybrid',
) -> Dict[str, Any]:
    """
    主触发函数 - 根据输入检测并加载相关知识。
    
    Args:
        user_input: 用户输入的文本
        project_dir: 项目目录路径
        explicit_triggers: 显式指定的触发关键字
        limit: 每类知识返回的条目数限制
        mode: 搜索模式 — 'keyword', 'semantic', 'hybrid'（默认 hybrid）
    
    Returns:
        检测结果和匹配的知识
    """
    result: Dict[str, Any] = {
        'detected': {
            'keywords': [],
            'scenarios': [],
            'problems': [],
            'tech_stack': None,
            'action_type': None
        },
        'knowledge': {
            'high_relevance': [],
            'medium_relevance': [],
            'by_category': {}
        },
        'triggers_used': [],
        'search_mode': mode,
    }
    
    all_triggers: Set[str] = set()
    
    # 1. 处理显式触发关键字
    if explicit_triggers:
        all_triggers.update(explicit_triggers)
    
    # 2. 从用户输入提取
    if user_input:
        keywords = extract_keywords(user_input)
        result['detected']['keywords'] = keywords
        all_triggers.update(keywords)
        
        scenarios = detect_scenarios(user_input)
        result['detected']['scenarios'] = scenarios
        all_triggers.update(scenarios)
        
        problems = detect_problems(user_input)
        result['detected']['problems'] = problems
        all_triggers.update(problems)
        
        action_type = detect_action_type(user_input)
        result['detected']['action_type'] = action_type
    
    # 3. 从项目检测
    if project_dir:
        tech_detection = detect_project_tech(project_dir)
        if 'error' not in tech_detection:
            result['detected']['tech_stack'] = tech_detection
            all_triggers.update(tech_detection.get('base_tech', []))
            all_triggers.update(tech_detection.get('frameworks', []))
            all_triggers.update(tech_detection.get('tools', []))
    
    result['triggers_used'] = sorted(list(all_triggers))
    
    # 4. 查询知识库 — 根据 mode 选择路径
    raw_query = user_input or ' '.join(sorted(all_triggers))
    matched: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    if mode == 'semantic' and raw_query:
        matched = query_semantic(raw_query, limit=limit * 2)
    elif mode == 'hybrid' and raw_query:
        matched = query_hybrid(raw_query, limit=limit * 2)
    elif all_triggers:
        matched = query_by_triggers(list(all_triggers), limit=limit * 2)
    
    # Deduplicate and split by relevance
    high_threshold = 0.45 if mode in ('semantic', 'hybrid') else 3
    for entry in matched:
        eid = entry.get('id', '')
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        score = entry.get('_relevance_score', 0) if mode in ('semantic', 'hybrid') else entry.get('_match_score', 0)
        if score >= high_threshold:
            result['knowledge']['high_relevance'].append(entry)
        else:
            result['knowledge']['medium_relevance'].append(entry)
    
    result['knowledge']['high_relevance'] = result['knowledge']['high_relevance'][:limit]
    result['knowledge']['medium_relevance'] = result['knowledge']['medium_relevance'][:limit]
    
    # 5. 根据检测到的场景/问题补充查询
    if result['detected']['scenarios']:
        for scenario in result['detected']['scenarios'][:2]:
            entries = query_by_category('scenario', limit=2)
            if entries:
                result['knowledge']['by_category'][f'scenario:{scenario}'] = entries
    
    if result['detected']['problems']:
        for problem in result['detected']['problems'][:2]:
            entries = query_by_category('problem', limit=2)
            if entries:
                result['knowledge']['by_category'][f'problem:{problem}'] = entries
    
    return result


CONTEXT_BUDGET = 3000  # total character budget for the context output
PROJECT_EXPERIENCE_HEADER = "## 项目经验"
PROJECT_EXPERIENCE_BUDGET = 2000  # character budget for project experience section


def _format_entry(content: Dict[str, Any], char_limit: int) -> List[str]:
    """Format a single entry's content fields within a character budget."""
    lines: List[str] = []
    used = 0

    for field, label in [('solution', '解决方案'), ('description', '描述'),
                         ('summary', '摘要'), ('typical_approach', '典型方法')]:
        text = content.get(field, '')
        if not text or not isinstance(text, str):
            continue
        available = char_limit - used
        if available <= 50:
            break
        truncated = text[:available]
        if len(text) > available:
            truncated = truncated.rsplit('。', 1)[0] or truncated
            truncated += '…'
        lines.append(f"**{label}**: {truncated}")
        used += len(truncated)

    if 'best_practices' in content:
        practices = content['best_practices'][:3]
        if practices and (char_limit - used) > 60:
            lines.append("**最佳实践**:")
            for p in practices:
                if (char_limit - used) < 40:
                    break
                lines.append(f"- {p}")
                used += len(p)

    if 'symptoms' in content:
        symptoms = content['symptoms'][:3]
        if symptoms and (char_limit - used) > 40:
            lines.append(f"**症状**: {'; '.join(symptoms)}")
            used += sum(len(s) for s in symptoms)

    if 'pitfalls' in content:
        pitfalls = content['pitfalls'][:2]
        if pitfalls and (char_limit - used) > 40:
            lines.append("**注意事项**:")
            for p in pitfalls:
                if (char_limit - used) < 30:
                    break
                lines.append(f"- {p}")
                used += len(p)

    if 'lessons' in content:
        lessons = content['lessons'][:2]
        if lessons and (char_limit - used) > 40:
            lines.append("**教训**:")
            for lesson in lessons:
                if (char_limit - used) < 30:
                    break
                lines.append(f"- {lesson}")
                used += len(lesson)

    return lines


def format_for_context(knowledge_result: Dict[str, Any]) -> str:
    """将知识结果格式化为可嵌入上下文的格式，使用动态字符预算。"""
    lines: List[str] = []

    high_rel = knowledge_result.get('knowledge', {}).get('high_relevance', [])
    med_rel = knowledge_result.get('knowledge', {}).get('medium_relevance', [])

    total_entries = len(high_rel) + len(med_rel)
    if total_entries == 0:
        return ''

    high_budget = int(CONTEXT_BUDGET * 0.7) if med_rel else CONTEXT_BUDGET
    med_budget = CONTEXT_BUDGET - high_budget

    if high_rel:
        per_entry = high_budget // min(len(high_rel), 5)
        lines.append("## 相关知识")
        for entry in high_rel[:5]:
            name = entry.get('name', 'Unknown')
            category = entry.get('category', '')
            content = entry.get('content', {})
            lines.append(f"\n### [{category}] {name}")
            lines.extend(_format_entry(content, per_entry))

    if med_rel:
        per_entry = med_budget // min(len(med_rel), 3)
        lines.append("\n## 可能相关")
        for entry in med_rel[:3]:
            name = entry.get('name', 'Unknown')
            category = entry.get('category', '')
            content = entry.get('content', {})
            lines.append(f"\n### [{category}] {name}")
            lines.extend(_format_entry(content, per_entry))

    return '\n'.join(lines)


def _extract_project_experience(filepath: str) -> str:
    """Extract the project experience section from an existing context file."""
    try:
        text = Path(filepath).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ''

    idx = text.find(PROJECT_EXPERIENCE_HEADER)
    if idx == -1:
        return ''

    section = text[idx:]
    if len(section) > PROJECT_EXPERIENCE_BUDGET:
        lines = section.split('\n')
        trimmed: List[str] = []
        total = 0
        for line in lines:
            if total + len(line) > PROJECT_EXPERIENCE_BUDGET:
                break
            trimmed.append(line)
            total += len(line) + 1
        section = '\n'.join(trimmed)

    return section


def format_for_context_with_merge(
    knowledge_result: Dict[str, Any],
    merge_file: Optional[str] = None,
) -> str:
    """Format knowledge for context, preserving project experience from an existing file."""
    parts: List[str] = []

    kb_section = format_for_context(knowledge_result)
    if kb_section:
        parts.append(kb_section)

    if merge_file:
        project_exp = _extract_project_experience(merge_file)
        if project_exp:
            parts.append('')
            parts.append(project_exp)

    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(
        description='Detect and trigger relevant knowledge based on input',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python knowledge_trigger.py --input "帮我修复这个 CORS 跨域问题"
  python knowledge_trigger.py --project /path/to/react-app
  python knowledge_trigger.py --input "如何优化 API 性能" --project .
  python knowledge_trigger.py --trigger react,hooks,performance
  python knowledge_trigger.py --input "..." --format context
  python knowledge_trigger.py --input "..." --format context --merge .opencode/.knowledge-context.md
        """
    )
    
    parser.add_argument('--input', '-i', help='User input text')
    parser.add_argument('--project', '-p', help='Project directory path')
    parser.add_argument('--trigger', '-t', help='Comma-separated explicit triggers')
    parser.add_argument('--limit', '-l', type=int, default=5, help='Result limit')
    parser.add_argument('--format', '-f', choices=['json', 'context', 'triggers'],
                        default='json', help='Output format')
    parser.add_argument('--mode', '-m', choices=['keyword', 'semantic', 'hybrid'],
                        default='hybrid', help='Search mode (default: hybrid)')
    parser.add_argument('--merge', help='Path to existing context file; '
                        'project experience section is preserved across sessions')
    
    args = parser.parse_args()
    
    if not any([args.input, args.project, args.trigger]):
        parser.print_help()
        sys.exit(1)
    
    explicit_triggers = None
    if args.trigger:
        explicit_triggers = [t.strip() for t in args.trigger.split(',')]
    
    result = trigger_knowledge(
        user_input=args.input,
        project_dir=args.project,
        explicit_triggers=explicit_triggers,
        limit=args.limit,
        mode=args.mode,
    )
    
    if args.format == 'json':
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif args.format == 'context':
        if args.merge:
            print(format_for_context_with_merge(result, args.merge))
        else:
            print(format_for_context(result))
    elif args.format == 'triggers':
        print(','.join(result.get('triggers_used', [])))


if __name__ == '__main__':
    main()
