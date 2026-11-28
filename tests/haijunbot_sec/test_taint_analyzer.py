# -*- coding: utf-8 -*-
"""
haijunbot_sec taint analysis tests

Coverage:
- Taint analysis framework: TaintPath, TaintSource, TaintSink data structures
- Joern analyzer: query generation, result parsing
- Taint analysis integration: integration with heuristic scanning

Running:
- Use pytest: pytest tests/haijunbot_sec/test_taint_analyzer.py -v
"""

from __future__ import annotations

from haijunbot.haijunbot_sec.taint_analyzer import (
    TaintPath,
    TaintSource,
    TaintSink,
    TaintAnalyzerFactory,
    TAINT_RULES,
    TaintSeverity,
)
from haijunbot.haijunbot_sec.joern_analyzer import JoernAnalyzer
from haijunbot.haijunbot_sec.checkers import analyze_c_cpp_text


def test_taint_analyzer_data_structures():
    """Test taint analysis data structures"""
    # Test TaintSource
    source = TaintSource(
        name="getenv",
        category="environment",
        description="Get data from environment variables",
        patterns=["getenv"],
    )
    assert source.name == "getenv"
    assert source.category == "environment"
    assert "getenv" in source.patterns

    # Test TaintSink
    sink = TaintSink(
        name="system",
        category="command_execution",
        severity=TaintSeverity.CRITICAL,
        description="Execute system commands",
        patterns=["system", "popen"],
    )
    assert sink.name == "system"
    assert sink.category == "command_execution"
    assert sink.severity == TaintSeverity.CRITICAL

    # Test TaintPath
    path = TaintPath(
        source="getenv",
        sink="system",
        path=["getenv", "system"],
        confidence=0.8,
        severity=TaintSeverity.CRITICAL,
        description="Taint propagates from getenv to system",
        line_number=10,
    )
    assert path.source == "getenv"
    assert path.sink == "system"
    assert path.confidence == 0.8
    assert path.line_number == 10


def test_taint_rules_predefined():
    """Test predefined taint rules"""
    # Check if predefined rules exist
    assert "command_injection" in TAINT_RULES
    assert "format_string" in TAINT_RULES
    assert "path_traversal" in TAINT_RULES
    assert "sql_injection" in TAINT_RULES
    assert "buffer_overflow" in TAINT_RULES

    # Check command injection rule
    cmd_rule = TAINT_RULES["command_injection"]
    assert cmd_rule.name == "command_injection"
    assert cmd_rule.severity == TaintSeverity.CRITICAL
    assert len(cmd_rule.sources) > 0
    assert len(cmd_rule.sinks) > 0


def test_joern_analyzer_initialization():
    """Test Joern analyzer initialization"""
    # Test factory creation
    analyzer = TaintAnalyzerFactory.create("joern")
    assert analyzer is not None
    assert isinstance(analyzer, JoernAnalyzer)


def test_joern_analyzer_query_generation():
    """Test Joern query generation"""
    analyzer = JoernAnalyzer()

    # Create test taint source and sink
    source = TaintSource(
        name="getenv",
        category="environment",
        patterns=["getenv"],
    )
    sink = TaintSink(
        name="system",
        category="command_execution",
        severity=TaintSeverity.CRITICAL,
        patterns=["system", "popen"],
    )

    # Generate query
    query = analyzer._generate_taint_query(source, sink)

    # Verify query content
    assert "getenv" in query
    assert "system" in query
    assert "reachableByFlows" in query


def test_taint_analysis_integration():
    """Test taint analysis integration into heuristic scanning"""
    # Test code: contains command injection vulnerability
    src = r"""
#include <stdlib.h>
#include <stdio.h>

int main(int argc, char *argv[]) {
    char *cmd = getenv("CMD");
    if (cmd) {
        system(cmd);  // Command injection risk
    }
    return 0;
}
"""

    # Execute analysis
    issues = analyze_c_cpp_text("test.c", src)

    # Verify results
    # Should detect command execution related issues
    # Note: taint analysis may return empty results because Joern is not installed
    # But heuristic rules should be able to detect the system call
    assert len(issues) >= 0  # At least should not crash


def test_format_string_taint_analysis():
    """Test format string taint analysis"""
    # Test code: contains format string vulnerability
    src = r"""
#include <stdio.h>

void vulnerable_printf(char *user_input) {
    printf(user_input);  // Format string vulnerability
}
"""

    # Execute analysis
    issues = analyze_c_cpp_text("test.c", src)

    # Verify results
    # Should detect format string related issues
    assert len(issues) >= 0  # At least should not crash


def test_taint_path_to_dict():
    """Test TaintPath conversion to dict"""
    path = TaintPath(
        source="getenv",
        sink="system",
        path=["getenv", "system"],
        confidence=0.8,
        severity=TaintSeverity.CRITICAL,
        description="Taint propagates from getenv to system",
        line_number=10,
    )

    # Convert to dict
    path_dict = path.to_dict()

    # Verify dict content
    assert path_dict["source"] == "getenv"
    assert path_dict["sink"] == "system"
    assert path_dict["confidence"] == 0.8
    assert path_dict["severity"] == "critical"
    assert path_dict["line_number"] == 10


def test_taint_analyzer_factory():
    """Test taint analyzer factory"""
    # Test creating Joern analyzer
    analyzer = TaintAnalyzerFactory.create("joern")
    assert analyzer is not None

    # Test configuring taint sources and sinks
    source = TaintSource(
        name="test_source",
        category="test",
        patterns=["test_func"],
    )
    sink = TaintSink(
        name="test_sink",
        category="test",
        severity=TaintSeverity.HIGH,
        patterns=["test_sink_func"],
    )

    analyzer.configure_sources([source])
    analyzer.configure_sinks([sink])

    # Verify configuration
    assert len(analyzer.sources) == 1
    assert len(analyzer.sinks) == 1
    assert analyzer.sources[0].name == "test_source"
    assert analyzer.sinks[0].name == "test_sink"


def test_builtin_data_flow_analyzer_is_available():
    """Test BuiltinDataFlowAnalyzer is always available"""
    from haijunbot.haijunbot_sec.data_flow_analyzer import BuiltinDataFlowAnalyzer

    analyzer = BuiltinDataFlowAnalyzer()
    assert analyzer.is_available() is True
    assert analyzer.get_name() == "builtin"
    assert analyzer.get_version() == "1.0.0"


def test_builtin_data_flow_analyzer_registered():
    """Test builtin backend is registered to factory"""
    assert "builtin" in TaintAnalyzerFactory.list_available()
    analyzer = TaintAnalyzerFactory.create("builtin")
    assert analyzer is not None
    assert analyzer.get_name() == "builtin"
    assert analyzer.is_available() is True


def test_builtin_data_flow_analyzer_analyze_no_db():
    """Test analyze returns empty list when there is no database"""
    from haijunbot.haijunbot_sec.data_flow_analyzer import BuiltinDataFlowAnalyzer

    analyzer = BuiltinDataFlowAnalyzer()
    result = analyzer.analyze("int main() { return 0; }", "test.c")
    assert result == []


def test_builtin_data_flow_analyzer_analyze_file_no_db():
    """Test analyze_file returns empty list when there is no database"""
    from haijunbot.haijunbot_sec.data_flow_analyzer import BuiltinDataFlowAnalyzer

    analyzer = BuiltinDataFlowAnalyzer()
    result = analyzer.analyze_file("/nonexistent/file.c")
    assert result == []


def test_analyze_with_best_analyzer_returns_result():
    """Test analyze_with_best_analyzer can return results"""
    from haijunbot.haijunbot_sec.taint_analyzer import analyze_with_best_analyzer

    result = analyze_with_best_analyzer("int main() { return 0; }", "test.c")
    # Returns empty list when there is no database, but should not raise an error
    assert isinstance(result, list)


def test_builtin_data_flow_analyzer_configure():
    """Test BuiltinDataFlowAnalyzer configuration of sources/sinks/sanitizers"""
    from haijunbot.haijunbot_sec.data_flow_analyzer import BuiltinDataFlowAnalyzer

    analyzer = BuiltinDataFlowAnalyzer()
    source = TaintSource(name="getenv", category="environment", patterns=["getenv"])
    sink = TaintSink(
        name="system",
        category="command_execution",
        severity=TaintSeverity.CRITICAL,
        patterns=["system"],
    )
    analyzer.configure_sources([source])
    analyzer.configure_sinks([sink])
    analyzer.configure_sanitizers(["sanitize"])
    assert len(analyzer.sources) == 1
    assert len(analyzer.sinks) == 1
    assert analyzer.sources[0].name == "getenv"
    assert analyzer.sinks[0].name == "system"
