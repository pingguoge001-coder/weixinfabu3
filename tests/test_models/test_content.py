"""Tests for Content model"""
import pytest
import json
from models.content import Content
from models.enums import Channel


class TestContentCreation:
    """Test Content creation and default values"""

    def test_content_creation_defaults(self):
        """Test Content creation with default values"""
        content = Content()

        assert content.content_code == ""
        assert content.text == ""
        assert content.image_paths == []
        assert content.channel == Channel.moment

    def test_content_creation_with_values(self, sample_content):
        """Test Content creation with provided values"""
        assert sample_content.content_code == "CONTENT001"
        assert sample_content.text == "This is test content"
        assert len(sample_content.image_paths) == 2
        assert sample_content.channel == Channel.moment

    def test_content_creation_text_only(self):
        """Test Content creation with text only"""
        content = Content(
            content_code="TEXT001",
            text="Text only content",
            channel=Channel.moment
        )

        assert content.content_code == "TEXT001"
        assert content.text == "Text only content"
        assert content.image_paths == []

    def test_content_creation_images_only(self):
        """Test Content creation with images only"""
        content = Content(
            content_code="IMG001",
            image_paths=["image1.jpg", "image2.jpg"],
            channel=Channel.moment
        )

        assert content.content_code == "IMG001"
        assert content.text == ""
        assert len(content.image_paths) == 2


class TestContentValidation:
    """Test Content validation"""

    def test_content_validate_empty_code(self):
        """Test validation fails when content_code is empty"""
        content = Content(text="Some text")
        is_valid, error = content.validate()

        assert is_valid is False
        assert error == "内容编码不能为空"

    def test_content_validate_empty_content(self):
        """Test validation fails when both text and images are empty"""
        content = Content(content_code="TEST001")
        is_valid, error = content.validate()

        assert is_valid is False
        assert error == "文本和图片不能同时为空"

    def test_content_validate_too_many_images(self):
        """Test validation fails when moment has more than 9 images"""
        content = Content(
            content_code="TEST001",
            image_paths=[f"image{i}.jpg" for i in range(10)],
            channel=Channel.moment
        )
        is_valid, error = content.validate()

        assert is_valid is False
        assert error == "朋友圈最多支持 9 张图片"

    def test_content_validate_exactly_nine_images(self):
        """Test validation passes with exactly 9 images for moment"""
        content = Content(
            content_code="TEST001",
            image_paths=[f"image{i}.jpg" for i in range(9)],
            channel=Channel.moment
        )
        is_valid, error = content.validate()

        assert is_valid is True
        assert error is None

    def test_content_validate_group_many_images(self):
        """Test validation passes for group with more than 9 images"""
        content = Content(
            content_code="TEST001",
            image_paths=[f"image{i}.jpg" for i in range(15)],
            channel=Channel.group
        )
        is_valid, error = content.validate()

        assert is_valid is True
        assert error is None

    def test_content_validate_text_only(self):
        """Test validation passes with text only"""
        content = Content(
            content_code="TEST001",
            text="Some text",
            channel=Channel.moment
        )
        is_valid, error = content.validate()

        assert is_valid is True
        assert error is None

    def test_content_validate_images_only(self):
        """Test validation passes with images only"""
        content = Content(
            content_code="TEST001",
            image_paths=["image1.jpg"],
            channel=Channel.moment
        )
        is_valid, error = content.validate()

        assert is_valid is True
        assert error is None

    def test_content_validate_text_and_images(self):
        """Test validation passes with both text and images"""
        content = Content(
            content_code="TEST001",
            text="Some text",
            image_paths=["image1.jpg"],
            channel=Channel.moment
        )
        is_valid, error = content.validate()

        assert is_valid is True
        assert error is None


class TestContentImageManagement:
    """Test Content image management methods"""

    def test_content_image_paths_json(self, sample_content):
        """Test image_paths_json returns valid JSON string"""
        json_str = sample_content.image_paths_json()

        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0] == "path/to/image1.jpg"

    def test_content_image_paths_json_empty(self):
        """Test image_paths_json with empty list"""
        content = Content(content_code="TEST001")
        json_str = content.image_paths_json()

        assert json_str == "[]"
        parsed = json.loads(json_str)
        assert parsed == []

    def test_content_image_paths_json_unicode(self):
        """Test image_paths_json with unicode characters"""
        content = Content(
            content_code="TEST001",
            image_paths=["路径/图片.jpg", "path/测试.png"]
        )
        json_str = content.image_paths_json()

        parsed = json.loads(json_str)
        assert parsed[0] == "路径/图片.jpg"
        assert parsed[1] == "path/测试.png"

    def test_content_add_image(self):
        """Test add_image adds image path"""
        content = Content(content_code="TEST001")
        assert len(content.image_paths) == 0

        content.add_image("image1.jpg")
        assert len(content.image_paths) == 1
        assert "image1.jpg" in content.image_paths

    def test_content_add_image_multiple(self):
        """Test add_image adds multiple images"""
        content = Content(content_code="TEST001")

        content.add_image("image1.jpg")
        content.add_image("image2.jpg")
        content.add_image("image3.jpg")

        assert len(content.image_paths) == 3
        assert content.image_paths == ["image1.jpg", "image2.jpg", "image3.jpg"]

    def test_content_add_image_duplicate(self):
        """Test add_image ignores duplicate paths"""
        content = Content(content_code="TEST001")

        content.add_image("image1.jpg")
        content.add_image("image1.jpg")  # Duplicate

        assert len(content.image_paths) == 1
        assert content.image_paths == ["image1.jpg"]

    def test_content_add_image_empty_string(self):
        """Test add_image ignores empty string"""
        content = Content(content_code="TEST001")

        content.add_image("")
        assert len(content.image_paths) == 0

    def test_content_remove_image(self):
        """Test remove_image removes existing image"""
        content = Content(
            content_code="TEST001",
            image_paths=["image1.jpg", "image2.jpg"]
        )

        result = content.remove_image("image1.jpg")

        assert result is True
        assert len(content.image_paths) == 1
        assert "image1.jpg" not in content.image_paths
        assert "image2.jpg" in content.image_paths

    def test_content_remove_image_not_exists(self):
        """Test remove_image returns False for non-existent image"""
        content = Content(
            content_code="TEST001",
            image_paths=["image1.jpg"]
        )

        result = content.remove_image("image2.jpg")

        assert result is False
        assert len(content.image_paths) == 1

    def test_content_clear_images(self):
        """Test clear_images removes all images"""
        content = Content(
            content_code="TEST001",
            image_paths=["image1.jpg", "image2.jpg", "image3.jpg"]
        )

        content.clear_images()

        assert len(content.image_paths) == 0
        assert content.image_paths == []


class TestContentProperties:
    """Test Content properties"""

    def test_content_has_images_property_true(self, sample_content):
        """Test has_images returns True when images exist"""
        assert sample_content.has_images is True

    def test_content_has_images_property_false(self):
        """Test has_images returns False when no images"""
        content = Content(content_code="TEST001", text="Text only")
        assert content.has_images is False

    def test_content_image_count_property(self, sample_content):
        """Test image_count returns correct count"""
        assert sample_content.image_count == 2

    def test_content_image_count_zero(self):
        """Test image_count returns 0 when no images"""
        content = Content(content_code="TEST001")
        assert content.image_count == 0


class TestContentSerialization:
    """Test Content serialization and deserialization"""

    def test_content_to_dict(self, sample_content):
        """Test to_dict serialization"""
        content_dict = sample_content.to_dict()

        assert isinstance(content_dict, dict)
        assert content_dict["content_code"] == "CONTENT001"
        assert content_dict["text"] == "This is test content"
        assert content_dict["channel"] == "moment"
        assert isinstance(content_dict["image_paths"], list)
        assert len(content_dict["image_paths"]) == 2

    def test_content_to_dict_empty_images(self):
        """Test to_dict with empty image list"""
        content = Content(
            content_code="TEST001",
            text="Text only"
        )
        content_dict = content.to_dict()

        assert content_dict["image_paths"] == []

    def test_content_from_dict(self):
        """Test from_dict deserialization"""
        data = {
            "content_code": "TEST001",
            "text": "Test text",
            "image_paths": ["image1.jpg", "image2.jpg"],
            "channel": "moment"
        }

        content = Content.from_dict(data)

        assert content.content_code == "TEST001"
        assert content.text == "Test text"
        assert len(content.image_paths) == 2
        assert content.channel == Channel.moment

    def test_content_from_dict_with_json_string(self):
        """Test from_dict with image_paths as JSON string"""
        data = {
            "content_code": "TEST001",
            "text": "Test text",
            "image_paths": '["image1.jpg", "image2.jpg", "image3.jpg"]',
            "channel": "moment"
        }

        content = Content.from_dict(data)

        assert content.content_code == "TEST001"
        assert isinstance(content.image_paths, list)
        assert len(content.image_paths) == 3
        assert content.image_paths[0] == "image1.jpg"

    def test_content_from_dict_with_invalid_json(self):
        """Test from_dict with invalid JSON string"""
        data = {
            "content_code": "TEST001",
            "text": "Test text",
            "image_paths": "invalid json",
            "channel": "moment"
        }

        content = Content.from_dict(data)

        assert content.content_code == "TEST001"
        assert content.image_paths == []  # Falls back to empty list

    def test_content_from_dict_with_enum_object(self):
        """Test from_dict with enum object (not string)"""
        data = {
            "content_code": "TEST001",
            "text": "Test text",
            "channel": Channel.group
        }

        content = Content.from_dict(data)

        assert content.channel == Channel.group

    def test_content_round_trip_serialization(self, sample_content):
        """Test round-trip serialization (to_dict -> from_dict)"""
        content_dict = sample_content.to_dict()
        restored_content = Content.from_dict(content_dict)

        assert restored_content.content_code == sample_content.content_code
        assert restored_content.text == sample_content.text
        assert restored_content.channel == sample_content.channel
        assert restored_content.image_paths == sample_content.image_paths


class TestContentEdgeCases:
    """Test Content edge cases and boundary conditions"""

    def test_content_with_very_long_text(self):
        """Test content with very long text"""
        long_text = "x" * 100000
        content = Content(
            content_code="TEST001",
            text=long_text
        )

        assert content.text == long_text
        assert len(content.text) == 100000

    def test_content_with_unicode_text(self):
        """Test content with unicode characters"""
        content = Content(
            content_code="测试001",
            text="这是测试文案，包含中文和 emoji 🎉🎊",
            channel=Channel.moment
        )

        assert content.content_code == "测试001"
        assert "emoji 🎉🎊" in content.text

    def test_content_with_special_characters(self):
        """Test content with special characters"""
        content = Content(
            content_code="TEST001",
            text="Special chars: @#$%^&*()[]{}|\\;:'\"<>,.?/",
        )

        assert "@#$%^&*" in content.text

    def test_content_with_newlines_and_tabs(self):
        """Test content with newlines and tabs"""
        content = Content(
            content_code="TEST001",
            text="Line 1\nLine 2\tTabbed\nLine 3"
        )

        assert "\n" in content.text
        assert "\t" in content.text

    def test_content_image_paths_order_preserved(self):
        """Test that image_paths order is preserved"""
        paths = ["z.jpg", "a.jpg", "m.jpg", "c.jpg"]
        content = Content(
            content_code="TEST001",
            image_paths=paths.copy()
        )

        assert content.image_paths == paths

    def test_content_add_remove_operations(self):
        """Test multiple add and remove operations"""
        content = Content(content_code="TEST001")

        # Add images
        for i in range(5):
            content.add_image(f"image{i}.jpg")
        assert len(content.image_paths) == 5

        # Remove some
        content.remove_image("image1.jpg")
        content.remove_image("image3.jpg")
        assert len(content.image_paths) == 3
        assert "image0.jpg" in content.image_paths
        assert "image2.jpg" in content.image_paths
        assert "image4.jpg" in content.image_paths

        # Add more
        content.add_image("image5.jpg")
        assert len(content.image_paths) == 4

        # Clear all
        content.clear_images()
        assert len(content.image_paths) == 0

    def test_content_validation_boundary_cases(self):
        """Test validation at boundary conditions"""
        # Test with exactly 1 image
        content = Content(
            content_code="TEST001",
            image_paths=["image1.jpg"],
            channel=Channel.moment
        )
        is_valid, _ = content.validate()
        assert is_valid is True

        # Test with exactly 9 images
        content.image_paths = [f"image{i}.jpg" for i in range(9)]
        is_valid, _ = content.validate()
        assert is_valid is True

        # Test with 10 images (boundary exceeded)
        content.image_paths.append("image9.jpg")
        is_valid, error = content.validate()
        assert is_valid is False
        assert "9 张图片" in error
