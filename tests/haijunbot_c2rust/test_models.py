# -*- coding: utf-8 -*-
"""haijunbot_c2rust.models module unit tests"""

from haijunbot.haijunbot_c2rust.models import FnRecord


class TestFnRecord:
    """Test FnRecord dataclass"""

    def test_basic_creation(self):
        """Test basic creation"""
        rec = FnRecord(
            id=1,
            name="test_func",
            qname="test::test_func",
            file="test.c",
            start_line=10,
            start_col=5,
            end_line=20,
            end_col=15,
            refs=["ref1", "ref2"],
        )
        assert rec.id == 1
        assert rec.name == "test_func"
        assert rec.qname == "test::test_func"
        assert rec.file == "test.c"
        assert rec.start_line == 10
        assert rec.start_col == 5
        assert rec.end_line == 20
        assert rec.end_col == 15
        assert rec.refs == ["ref1", "ref2"]

    def test_default_values(self):
        """Test default values"""
        rec = FnRecord(
            id=1,
            name="test_func",
            qname="test_func",
            file="test.c",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            refs=[],
        )
        assert rec.signature == ""
        assert rec.return_type == ""
        assert rec.params is None
        assert rec.lib_replacement is None

    def test_with_signature(self):
        """Test with signature"""
        rec = FnRecord(
            id=1,
            name="test_func",
            qname="test_func",
            file="test.c",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            refs=[],
            signature="int test_func(int x)",
            return_type="int",
            params=[{"name": "x", "type": "int"}],
        )
        assert rec.signature == "int test_func(int x)"
        assert rec.return_type == "int"
        assert rec.params == [{"name": "x", "type": "int"}]

    def test_with_lib_replacement(self):
        """Test with library replacement info"""
        lib_replacement = {
            "library": "std",
            "function": "memcpy",
            "confidence": 0.9,
        }
        rec = FnRecord(
            id=1,
            name="test_func",
            qname="test_func",
            file="test.c",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            refs=[],
            lib_replacement=lib_replacement,
        )
        assert rec.lib_replacement == lib_replacement

    def test_empty_refs(self):
        """Test empty reference list"""
        rec = FnRecord(
            id=1,
            name="test_func",
            qname="test_func",
            file="test.c",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            refs=[],
        )
        assert rec.refs == []

    def test_multiple_refs(self):
        """Test multiple references"""
        refs = ["func1", "func2", "func3", "func4", "func5"]
        rec = FnRecord(
            id=1,
            name="test_func",
            qname="test_func",
            file="test.c",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            refs=refs,
        )
        assert len(rec.refs) == 5
        assert rec.refs == refs

    def test_complex_qname(self):
        """Test complex qualified name"""
        rec = FnRecord(
            id=1,
            name="method",
            qname="namespace::Class::method",
            file="test.cpp",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            refs=[],
        )
        assert rec.qname == "namespace::Class::method"
        assert rec.name == "method"
