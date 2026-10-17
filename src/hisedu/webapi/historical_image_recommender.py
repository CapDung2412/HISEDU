from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, Sequence

from .schemas import HistoricalImage


MAX_RECOMMENDED_HISTORICAL_IMAGES = 4


def _normalized(value: str) -> str:
    """Return a comparison form that is stable across Vietnamese accents."""

    value = value.casefold().replace("đ", "d")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_phrase = _normalized(phrase)
    return bool(normalized_phrase) and f" {normalized_phrase} " in f" {text} "


@dataclass(frozen=True, slots=True)
class _CuratedImage:
    image: HistoricalImage
    collection_aliases: tuple[str, ...]
    subject_aliases: tuple[str, ...]


_ENGLISH_REVOLUTION = (
    "cách mạng tư sản Anh",
    "cách mạng Anh",
    "nội chiến Anh",
    "English Civil War",
    "Oliver Cromwell",
    "Naseby",
    "Charles I",
    "Sác-lơ I",
)

_FRENCH_REVOLUTION = (
    "cách mạng tư sản Pháp",
    "cách mạng Pháp",
    "French Revolution",
    "Bastille",
    "Tuyên ngôn Nhân quyền và Dân quyền",
    "Declaration of the Rights of Man",
)

_AMERICAN_REVOLUTION = (
    "chiến tranh giành độc lập của 13 thuộc địa",
    "chiến tranh giành độc lập ở Bắc Mỹ",
    "cách mạng tư sản Mỹ",
    "cách mạng Mỹ",
    "American Revolution",
    "Boston Tea Party",
    "sự kiện chè Boston",
)

_INDUSTRIAL_REVOLUTION = (
    "cách mạng công nghiệp",
    "Industrial Revolution",
    "máy kéo sợi Gien-ni",
    "máy kéo sợi Jenny",
    "Spinning Jenny",
)

_PARIS_COMMUNE = (
    "Công xã Pa-ri",
    "Công xã Paris",
    "Paris Commune",
    "Pa-ri năm 1871",
)

_MEIJI_RESTORATION = (
    "Duy tân Minh Trị",
    "cuộc Duy tân Minh Trị",
    "Meiji Restoration",
    "Thiên hoàng Minh Trị",
    "Emperor Meiji",
)

_WORLD_WAR_ONE = (
    "Chiến tranh thế giới thứ nhất",
    "Thế chiến thứ nhất",
    "World War I",
    "First World War",
    "chiến tranh chiến hào",
)


_CATALOG: tuple[_CuratedImage, ...] = (
    _CuratedImage(
        image=HistoricalImage(
            id="battle-of-naseby",
            title="Trận Naseby",
            description=(
                "Bản khắc mô tả trận Naseby năm 1645, thắng lợi quyết định của "
                "quân Quốc hội trong Nội chiến Anh."
            ),
            image_url="/historical/battle-of-naseby.jpg",
            source_url=(
                "https://commons.wikimedia.org/wiki/"
                "File:Edward_Radclyffe_-_Battle_of_Naseby_-_B1998.14.672_-_"
                "Yale_Center_for_British_Art.jpg"
            ),
            institution="Yale Center for British Art",
            license="CC0 1.0",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            creator="Edward Radclyffe",
            date="Thế kỷ XIX (mô tả sự kiện năm 1645)",
            media_type="engraving",
            alt="Bản khắc cảnh giao chiến trong trận Naseby năm 1645.",
            observation_prompt=(
                "Quan sát đội hình và vũ khí: hình ảnh gợi cho em điều gì về "
                "quy mô của Nội chiến Anh?"
            ),
            relevance=(
                "Minh họa bước ngoặt quân sự giúp lực lượng Quốc hội giành ưu thế "
                "trong Cách mạng tư sản Anh."
            ),
        ),
        collection_aliases=_ENGLISH_REVOLUTION,
        subject_aliases=("Naseby", "1645", "quân Quốc hội", "nội chiến"),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="oliver-cromwell-1649",
            title="Chân dung Oliver Cromwell",
            description=(
                "Chân dung Oliver Cromwell khoảng năm 1649, nhân vật lãnh đạo "
                "quan trọng của phe Quốc hội trong Cách mạng tư sản Anh."
            ),
            image_url="/historical/oliver-cromwell-1649.jpg",
            source_url=(
                "https://commons.wikimedia.org/wiki/"
                "File:Portrait_of_Oliver_Cromwell,_circa_1649.jpg"
            ),
            institution="Cromwell Museum",
            license="Public domain",
            license_url="https://creativecommons.org/publicdomain/mark/1.0/",
            creator="Không rõ tác giả",
            date="Khoảng năm 1649",
            media_type="portrait",
            alt="Chân dung Oliver Cromwell mặc áo giáp, khoảng năm 1649.",
            observation_prompt=(
                "Trang phục và cách khắc họa Cromwell cho thấy người đương thời "
                "muốn nhấn mạnh vai trò nào của ông?"
            ),
            relevance=(
                "Giúp nhận diện Oliver Cromwell và liên hệ vai trò của ông với phe "
                "Quốc hội trong Cách mạng tư sản Anh."
            ),
        ),
        collection_aliases=_ENGLISH_REVOLUTION,
        subject_aliases=("Oliver Cromwell", "Cromwell", "1649", "nhân vật"),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="storming-of-bastille",
            title="Nhân dân Paris đánh chiếm ngục Bastille",
            description=(
                "Tranh của Henry Singleton tái hiện cuộc tấn công ngục Bastille "
                "ngày 14/7/1789, sự kiện mở đầu Cách mạng tư sản Pháp."
            ),
            image_url="/historical/storming-of-bastille.jpg",
            source_url=(
                "https://commons.wikimedia.org/wiki/"
                "File:Henry_Singleton_the_Storming_of_the_Bastille.jpg"
            ),
            institution="Wikimedia Commons",
            license="Public domain",
            license_url="https://creativecommons.org/publicdomain/mark/1.0/",
            creator="Henry Singleton",
            date="Cuối thế kỷ XVIII (sự kiện ngày 14/7/1789)",
            media_type="painting",
            alt="Tranh tái hiện nhân dân Paris tấn công ngục Bastille năm 1789.",
            observation_prompt=(
                "Hãy tìm các chi tiết thể hiện sự tham gia của quần chúng và giải "
                "thích vì sao Bastille trở thành biểu tượng của cách mạng."
            ),
            relevance=(
                "Minh họa sự kiện ngày 14/7/1789, một mốc tiêu biểu của Cách mạng "
                "tư sản Pháp."
            ),
        ),
        collection_aliases=_FRENCH_REVOLUTION,
        subject_aliases=("Bastille", "14/7/1789", "1789", "nhân dân Paris"),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="declaration-rights-1789",
            title="Tuyên ngôn Nhân quyền và Dân quyền năm 1789",
            description=(
                "Bản trình bày Tuyên ngôn Nhân quyền và Dân quyền được Quốc hội "
                "Lập hiến Pháp thông qua tháng 8/1789."
            ),
            image_url="/historical/declaration-rights-1789.jpg",
            source_url=(
                "https://commons.wikimedia.org/wiki/"
                "File:Declaration_of_the_Rights_of_Man_and_of_the_Citizen_in_1789.jpg"
            ),
            institution="Musée Carnavalet – Histoire de Paris / Paris Musées",
            license="CC0 1.0",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            creator="Jean-Jacques-François Le Barbier (thiết kế được ghi nhận)",
            date="Năm 1789",
            media_type="document",
            alt="Bản Tuyên ngôn Nhân quyền và Dân quyền của Pháp năm 1789.",
            observation_prompt=(
                "Quan sát bố cục và biểu tượng trên văn kiện: các chi tiết ấy "
                "nhấn mạnh những tư tưởng mới nào?"
            ),
            relevance=(
                "Là tư liệu trực quan về tư tưởng tự do, bình đẳng và quyền con "
                "người của Cách mạng tư sản Pháp."
            ),
        ),
        collection_aliases=_FRENCH_REVOLUTION,
        subject_aliases=(
            "Tuyên ngôn Nhân quyền và Dân quyền",
            "nhân quyền",
            "dân quyền",
            "quyền con người",
            "1789",
        ),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="boston-tea-party",
            title="Sự kiện chè Boston",
            description=(
                "Tranh in màu của Nathaniel Currier năm 1846 tái hiện việc những "
                "người thuộc địa đổ các thùng chè xuống cảng Boston ngày 16/12/1773."
            ),
            image_url="/historical/boston-tea-party.jpg",
            source_url=(
                "https://commons.wikimedia.org/wiki/"
                "File:Boston_Tea_Party_Currier_colored.jpg"
            ),
            institution="Springfield Museums / Wikimedia Commons",
            license="Public domain",
            license_url="https://creativecommons.org/publicdomain/mark/1.0/",
            creator="Nathaniel Currier",
            date="Năm 1846 (tái hiện sự kiện năm 1773)",
            media_type="engraving",
            alt="Tranh in màu tái hiện sự kiện chè Boston tại bến cảng năm 1773.",
            observation_prompt=(
                "Tìm các chi tiết cho thấy hành động phản đối chính sách thuế của "
                "chính quốc Anh và nhận xét về cách tác giả tái hiện sự kiện."
            ),
            relevance=(
                "Minh họa một sự kiện làm mâu thuẫn giữa 13 thuộc địa và chính quốc "
                "Anh trở nên gay gắt trước chiến tranh giành độc lập."
            ),
        ),
        collection_aliases=_AMERICAN_REVOLUTION,
        subject_aliases=("Boston", "chè Boston", "16/12/1773", "1773", "thuế chè"),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="spinning-jenny",
            title="Mô hình máy kéo sợi Jenny",
            description=(
                "Ảnh chụp mô hình máy kéo sợi Jenny tại Bảo tàng Công nghiệp hóa "
                "thời kì đầu ở Wuppertal; đây là mô hình bảo tàng, không phải ảnh "
                "chụp ở thế kỷ XVIII."
            ),
            image_url="/historical/spinning-jenny.jpg",
            source_url="https://commons.wikimedia.org/wiki/File:Spinning_jenny.jpg",
            institution="Museum für Frühindustrialisierung, Wuppertal",
            license="CC BY-SA 3.0",
            license_url="https://creativecommons.org/licenses/by-sa/3.0/",
            creator="Markus Schweiß",
            date="Ảnh chụp trước ngày 14/7/2004",
            media_type="artifact",
            alt="Mô hình máy kéo sợi Jenny trưng bày trong bảo tàng ở Wuppertal.",
            observation_prompt=(
                "Quan sát số suốt sợi và cơ cấu quay: vì sao chiếc máy có thể giúp "
                "một công nhân kéo nhiều sợi cùng lúc?"
            ),
            relevance=(
                "Giúp hình dung sự cơ giới hóa ngành dệt trong giai đoạn đầu của "
                "Cách mạng công nghiệp."
            ),
        ),
        collection_aliases=_INDUSTRIAL_REVOLUTION,
        subject_aliases=("Jenny", "Gien-ni", "kéo sợi", "ngành dệt", "cơ giới hóa"),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="paris-commune-barricade",
            title="Chiến lũy của Công xã Paris năm 1871",
            description=(
                "Ảnh do Pierre-Ambroise Richebourg chụp một chiến lũy tại góc "
                "Hôtel-de-Ville và phố Rivoli trong thời kì Công xã Paris."
            ),
            image_url="/historical/paris-commune-barricade.jpg",
            source_url=(
                "https://commons.wikimedia.org/wiki/"
                "File:Barricade_Paris_1871_by_Pierre-Ambrose_Richebourg.jpg"
            ),
            institution="The Metropolitan Museum of Art",
            license="CC0 1.0",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            creator="Pierre-Ambroise Richebourg",
            date="Năm 1871",
            media_type="photograph",
            alt="Ảnh một chiến lũy lát đá trên đường phố Paris trong Công xã năm 1871.",
            observation_prompt=(
                "Quan sát vật liệu và vị trí chiến lũy: người dân Paris đã tận dụng "
                "không gian đô thị để phòng thủ như thế nào?"
            ),
            relevance=(
                "Là ảnh chụp đương thời giúp hình dung bối cảnh chiến đấu của Công "
                "xã Paris năm 1871."
            ),
        ),
        collection_aliases=_PARIS_COMMUNE,
        subject_aliases=("chiến lũy", "barricade", "1871", "Hôtel-de-Ville"),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="emperor-meiji",
            title="Thiên hoàng Minh Trị năm 1872",
            description=(
                "Chân dung do Uchida Kuichi chụp năm 1872, giai đoạn đầu của công "
                "cuộc Duy tân Minh Trị ở Nhật Bản."
            ),
            image_url="/historical/emperor-meiji.jpg",
            source_url="https://commons.wikimedia.org/wiki/File:Meiji_Emperor.jpg",
            institution="Wikimedia Commons",
            license="Public domain",
            license_url="https://creativecommons.org/publicdomain/mark/1.0/",
            creator="Uchida Kuichi",
            date="Năm 1872",
            media_type="portrait",
            alt="Ảnh chân dung Thiên hoàng Minh Trị ngồi trong bộ quân phục trang trọng năm 1872.",
            observation_prompt=(
                "Quan sát trang phục và tư thế của Thiên hoàng Minh Trị, sau đó "
                "liên hệ với quá trình Nhật Bản chuyển đổi trong thời kì cải cách."
            ),
            relevance=(
                "Giúp nhận diện nhân vật gắn với công cuộc Duy tân Minh Trị bắt đầu "
                "từ năm 1868."
            ),
        ),
        collection_aliases=_MEIJI_RESTORATION,
        subject_aliases=("Minh Trị", "Meiji", "Thiên hoàng", "1868", "1872"),
    ),
    _CuratedImage(
        image=HistoricalImage(
            id="world-war-one-trench",
            title="Chiến hào tại Flirey, Pháp năm 1918",
            description=(
                "Ảnh tư liệu từ kho lưu trữ của San Diego Air & Space Museum cho "
                "thấy một chiến hào tại Flirey, Pháp, mười ngày sau khi quân Mỹ "
                "chiếm giữ vị trí này năm 1918."
            ),
            image_url="/historical/world-war-one-trench.jpg",
            source_url="https://commons.wikimedia.org/wiki/File:World_War_One_Trench.jpg",
            institution="San Diego Air & Space Museum Archives",
            license="No known copyright restrictions",
            license_url="https://www.flickr.com/commons/usage/",
            creator="Không rõ tác giả",
            date="Năm 1918",
            media_type="photograph",
            alt="Ảnh đen trắng một chiến hào xây bằng bao cát tại Flirey, Pháp, năm 1918.",
            observation_prompt=(
                "Quan sát độ sâu, hệ thống bao cát và địa hình quanh chiến hào: "
                "điều kiện này tác động ra sao đến đời sống binh lính?"
            ),
            relevance=(
                "Giúp hình dung đặc trưng chiến tranh chiến hào và mức độ khốc liệt "
                "của Chiến tranh thế giới thứ nhất."
            ),
        ),
        collection_aliases=_WORLD_WAR_ONE,
        subject_aliases=("chiến hào", "trench", "1914", "1918", "binh lính"),
    ),
)


class HistoricalImageRecommendationService(Protocol):
    @property
    def provider_version(self) -> str: ...

    async def recommend(
        self,
        *,
        question: str,
        topics: Sequence[str] = (),
        limit: int = MAX_RECOMMENDED_HISTORICAL_IMAGES,
    ) -> list[HistoricalImage]: ...


class CuratedHistoricalImageRecommender:
    """Rank a small, reviewed local archive without network requests."""

    def __init__(self, catalog: Sequence[_CuratedImage] = _CATALOG) -> None:
        self._catalog = tuple(catalog)
        version_payload = [item.image.model_dump(mode="json") for item in self._catalog]
        digest = hashlib.sha256(
            json.dumps(version_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        self._provider_version = f"curated-historical-images-v1-{digest}"

    @property
    def provider_version(self) -> str:
        return self._provider_version

    async def recommend(
        self,
        *,
        question: str,
        topics: Sequence[str] = (),
        limit: int = MAX_RECOMMENDED_HISTORICAL_IMAGES,
    ) -> list[HistoricalImage]:
        requested_limit = max(0, min(int(limit), MAX_RECOMMENDED_HISTORICAL_IMAGES))
        if requested_limit == 0:
            return []

        question_text = _normalized(question)
        context_text = _normalized(" ".join((question, *topics)))
        ranked: list[tuple[int, int, HistoricalImage]] = []
        for catalog_index, item in enumerate(self._catalog):
            collection_hits = [
                alias
                for alias in item.collection_aliases
                if _contains_phrase(context_text, alias)
            ]
            # A reviewed image is returned only when its historical collection
            # is named explicitly. There is deliberately no generic fallback.
            if not collection_hits:
                continue
            subject_question_hits = sum(
                _contains_phrase(question_text, alias) for alias in item.subject_aliases
            )
            subject_context_hits = sum(
                _contains_phrase(context_text, alias) for alias in item.subject_aliases
            )
            collection_question_hits = sum(
                _contains_phrase(question_text, alias)
                for alias in item.collection_aliases
            )
            # The learner's own wording is the relevance gate. Retrieved
            # lesson titles only refine ranking; they cannot introduce an
            # image for a different event that happens to share one lesson.
            if not collection_question_hits:
                continue
            score = (
                collection_question_hits * 100
                + subject_question_hits * 20
                + subject_context_hits * 3
                + len(collection_hits)
            )
            ranked.append((score, -catalog_index, item.image))

        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [image for _, _, image in ranked[:requested_limit]]


__all__ = [
    "CuratedHistoricalImageRecommender",
    "HistoricalImageRecommendationService",
    "MAX_RECOMMENDED_HISTORICAL_IMAGES",
]
