"""
Unit tests for the metadata_scoring module.

Tests:
- Quality score calculation
- Upgrade decision logic
- Manual correction detection
- Date source descriptions
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from metadata_scoring import (
    calculate_metadata_quality_score,
    should_upgrade_archive_file,
    get_date_source_description,
    compare_metadata_scores,
    METADATA_SOURCE_SCORES
)
import constants


class TestCalculateMetadataQualityScore:
    """Tests for calculate_metadata_quality_score function."""

    def test_exif_score(self):
        """Test EXIF DateTimeOriginal gets highest base score."""
        score = calculate_metadata_quality_score('exif', True)
        assert score == constants.METADATA_SCORE_EXIF + constants.METADATA_RELIABILITY_BONUS

    def test_os_metadata_score(self):
        """Test OS metadata gets low score."""
        score = calculate_metadata_quality_score('os_metadata', True)
        assert score == constants.METADATA_SCORE_OS_METADATA + constants.METADATA_RELIABILITY_BONUS

    def test_fallback_score(self):
        """Test fallback gets zero base score."""
        score = calculate_metadata_quality_score('fallback', False)
        assert score == 0

    def test_reliability_bonus(self):
        """Test reliability bonus is added correctly."""
        reliable_score = calculate_metadata_quality_score('exif', True)
        unreliable_score = calculate_metadata_quality_score('exif', False)

        assert reliable_score - unreliable_score == constants.METADATA_RELIABILITY_BONUS

    def test_none_source(self):
        """Test None date source is treated as fallback."""
        score = calculate_metadata_quality_score(None, False)
        assert score == 0

    def test_unknown_source(self):
        """Test unknown source gets zero base score."""
        score = calculate_metadata_quality_score('unknown_source', True)
        assert score == constants.METADATA_RELIABILITY_BONUS  # Only reliability bonus

    def test_all_sources_have_scores(self):
        """Test all known sources produce valid scores."""
        for source in METADATA_SOURCE_SCORES.keys():
            score = calculate_metadata_quality_score(source, True)
            assert score >= 0
            assert score <= 100

    def test_score_ordering(self):
        """Test that score ordering makes sense."""
        exif_score = calculate_metadata_quality_score('exif', True)
        iptc_score = calculate_metadata_quality_score('iptc', True)
        xmp_score = calculate_metadata_quality_score('xmp', True)
        os_score = calculate_metadata_quality_score('os_metadata', True)

        # EXIF should be highest
        assert exif_score > iptc_score
        assert iptc_score > xmp_score
        assert xmp_score > os_score


class TestShouldUpgradeArchiveFile:
    """Tests for should_upgrade_archive_file function."""

    def test_upgrade_better_metadata(self):
        """Test upgrade when incoming has better metadata."""
        archive_metadata = {
            'date_source': 'os_metadata',
            'date_reliable': True,
            'metadata_quality_score': 40
        }

        should_upgrade, reason, score = should_upgrade_archive_file(
            archive_metadata,
            'exif',  # Better source
            True
        )

        assert should_upgrade is True
        assert 'better metadata' in reason.lower()

    def test_no_upgrade_worse_metadata(self):
        """Test no upgrade when incoming has worse metadata."""
        archive_metadata = {
            'date_source': 'exif',
            'date_reliable': True,
            'metadata_quality_score': 100
        }

        should_upgrade, reason, score = should_upgrade_archive_file(
            archive_metadata,
            'os_metadata',  # Worse source
            True
        )

        assert should_upgrade is False
        assert 'archive has better' in reason.lower()

    def test_upgrade_same_score_reliability_tiebreaker(self):
        """Test upgrade when same score but incoming is reliable."""
        archive_metadata = {
            'date_source': 'exif',
            'date_reliable': False,
            'metadata_quality_score': 80  # EXIF unreliable
        }

        should_upgrade, reason, score = should_upgrade_archive_file(
            archive_metadata,
            'exif',
            True  # Incoming is reliable
        )

        assert should_upgrade is True
        assert 'reliable' in reason.lower()

    def test_no_upgrade_same_quality(self):
        """Test no upgrade when same quality and both reliable."""
        archive_metadata = {
            'date_source': 'exif',
            'date_reliable': True,
            'metadata_quality_score': 100
        }

        should_upgrade, reason, score = should_upgrade_archive_file(
            archive_metadata,
            'exif',
            True
        )

        assert should_upgrade is False
        assert 'same quality' in reason.lower() or 'no improvement' in reason.lower()

    def test_compute_score_from_components(self):
        """Test score computation when metadata_quality_score is not provided."""
        archive_metadata = {
            'date_source': 'os_metadata',
            'date_reliable': True
            # No metadata_quality_score
        }

        should_upgrade, reason, score = should_upgrade_archive_file(
            archive_metadata,
            'exif',
            True
        )

        assert should_upgrade is True

    def test_returns_incoming_score(self):
        """Test that incoming score is returned."""
        archive_metadata = {
            'date_source': 'os_metadata',
            'date_reliable': True,
            'metadata_quality_score': 40
        }

        should_upgrade, reason, incoming_score = should_upgrade_archive_file(
            archive_metadata,
            'exif',
            True
        )

        expected_score = calculate_metadata_quality_score('exif', True)
        assert incoming_score == expected_score


class TestGetDateSourceDescription:
    """Tests for get_date_source_description function."""

    def test_known_sources(self):
        """Test descriptions for known sources."""
        known_sources = [
            'exif', 'exif_digitized', 'exif_gps', 'iptc', 'xmp',
            'os_metadata', 'video_metadata', 'fallback'
        ]

        for source in known_sources:
            desc = get_date_source_description(source)
            assert desc is not None
            assert len(desc) > 0
            assert 'unknown' not in desc.lower() or source == 'unknown'

    def test_unknown_source(self):
        """Test description for unknown source."""
        desc = get_date_source_description('completely_unknown')
        assert 'unknown' in desc.lower()

    def test_exif_description_is_clear(self):
        """Test that EXIF description mentions camera/capture."""
        desc = get_date_source_description('exif')
        assert 'camera' in desc.lower() or 'capture' in desc.lower() or 'original' in desc.lower()


class TestCompareMetadataScores:
    """Tests for compare_metadata_scores function."""

    def test_first_better(self):
        """Test comparison when first is better."""
        result = compare_metadata_scores(100, 50)
        assert 'first is better' in result.lower()
        assert '50' in result  # Difference shown

    def test_second_better(self):
        """Test comparison when second is better."""
        result = compare_metadata_scores(30, 80)
        assert 'second is better' in result.lower()

    def test_equal_scores(self):
        """Test comparison when scores are equal."""
        result = compare_metadata_scores(75, 75)
        assert 'equal' in result.lower()


class TestScoreConsistency:
    """Tests for overall score system consistency."""

    def test_max_score_is_100(self):
        """Test that maximum possible score is 100."""
        max_score = calculate_metadata_quality_score('exif', True)
        assert max_score == 100

    def test_min_score_is_0(self):
        """Test that minimum score is 0."""
        min_score = calculate_metadata_quality_score('fallback', False)
        assert min_score == 0

    def test_video_metadata_reasonable(self):
        """Test that video metadata score is reasonable compared to EXIF."""
        video_score = calculate_metadata_quality_score('video_metadata', True)
        exif_score = calculate_metadata_quality_score('exif', True)

        # Video metadata should be decent but not as good as photo EXIF
        assert 50 <= video_score <= 90
        assert video_score < exif_score
