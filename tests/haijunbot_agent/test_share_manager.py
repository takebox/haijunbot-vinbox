# -*- coding: utf-8 -*-
"""share_manager unit tests (mainly testing parse_selection)"""

from haijunbot.haijunbot_agent.share_manager import parse_selection


class TestParseSelection:
    """Tests for parse_selection"""

    def test_basic_range_and_values(self):
        assert parse_selection("1,2,3,4-6,20", 25) == [1, 2, 3, 4, 5, 6, 20]

    def test_out_of_bounds_ignored(self):
        # 0 and 26 out of bounds; 5-30 ignored entirely because end exceeds bounds; 3 preserved
        assert parse_selection("0,26,5-30,3", 25) == [3]

    def test_invalid_inputs(self):
        # Invalid entries ignored; valid range 2-3 parsed
        assert parse_selection("a,b,1-?,2-3", 10) == [2, 3]

    def test_spaces_around_hyphen_and_commas(self):
        assert parse_selection(" 2 - 4 , 6 ", 10) == [2, 3, 4, 6]

    def test_duplicates_removed(self):
        assert parse_selection("1,1,2,2,2,3-4,4-5", 10) == [1, 2, 3, 4, 5]

    def test_reverse_range_ignored(self):
        # 5-3 generates empty range in implementation, ignored
        assert parse_selection("1,5-3", 10) == [1]
