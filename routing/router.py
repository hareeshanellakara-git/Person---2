from .route_models import PageProfile, Region, RouteDecision


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _region_complexity(
    region: Region,
) -> float:
    score = 0.0

    if region.region_type in (
        "table",
        "formula",
        "chart",
        "figure",
    ):
        score += 0.35

    if region.source == "layout_model":
        score += 0.15

    if region.confidence < 0.60:
        score += 0.25

    if region.metadata.get(
        "order_ambiguous",
        False,
    ):
        score += 0.15

    if region.is_full_width:
        score += 0.05

    return _clamp(score)


def _choose_route(
    region: Region,
    profile: PageProfile,
    risk: str,
) -> tuple[str, str]:

    region_type = region.region_type

    if region_type == "table":
        return "table", "table_extractor"

    if region_type == "formula":
        return "equation", "equation_extractor"

    if region_type == "chart":
        return "chart", "chart_extractor"

    if region_type == "figure":
        return "figure", "figure_extractor"

    if profile.is_scanned:
        if risk in ("HIGH", "CRITICAL"):
            return "vlm", "vlm_fallback"

        return "ocr", "ocr_extractor"

    if region.source == "layout_model":
        if region.confidence < 0.50:
            return "vlm", "vlm_fallback"

    if region.confidence < 0.45:
        return "ocr", "ocr_extractor"

    if risk in ("HIGH", "CRITICAL"):
        return "vlm", "vlm_fallback"

    return "native", "native_text_extractor"


def _calculate_confidence(
    region: Region,
    profile: PageProfile,
    route: str,
    risk: str,
) -> float:

    confidence = 0.90

    confidence += (
        region.confidence - 0.75
    ) * 0.30

    if profile.is_scanned:
        if route == "ocr":
            confidence += 0.03

        elif route == "native":
            confidence -= 0.25

    if region.source == "layout_model":
        confidence += 0.02

    if risk == "HIGH":
        confidence -= 0.05

    elif risk == "CRITICAL":
        confidence -= 0.10

    complexity = _region_complexity(
        region
    )

    confidence -= complexity * 0.10

    return _clamp(confidence)


def _reason(
    region: Region,
    profile: PageProfile,
    route: str,
    risk: str,
) -> str:

    if region.region_type == "table":
        return "Region identified as table"

    if region.region_type == "formula":
        return "Region identified as equation or formula"

    if region.region_type == "chart":
        return "Region identified as chart"

    if region.region_type == "figure":
        return "Region identified as figure"

    if profile.is_scanned and route == "ocr":
        return "Scanned page requires OCR"

    if route == "vlm":
        if risk in ("HIGH", "CRITICAL"):
            return "High-risk or uncertain region requires visual fallback"

        return "Region requires visual fallback"

    if route == "ocr":
        return "Native extraction confidence is too low"

    return "Native document text is suitable"


def _priority(
    region: Region,
    risk: str,
) -> str:

    if risk == "CRITICAL":
        return "critical"

    if risk == "HIGH":
        return "high"

    if region.region_type in (
        "table",
        "formula",
        "chart",
    ):
        return "high"

    if region.metadata.get(
        "order_ambiguous",
        False,
    ):
        return "high"

    if risk == "MEDIUM":
        return "normal"

    return "normal"


def route_region(
    region: Region,
    profile: PageProfile,
    risk: str = "LOW",
) -> RouteDecision:

    route, extractor = _choose_route(
        region,
        profile,
        risk,
    )

    confidence = _calculate_confidence(
        region,
        profile,
        route,
        risk,
    )

    reason = _reason(
        region,
        profile,
        route,
        risk,
    )

    priority = _priority(
        region,
        risk,
    )

    return RouteDecision(
        region_id=region.region_id,
        route=route,
        extractor=extractor,
        confidence=confidence,
        reason=reason,
        priority=priority,
    )


def route_regions(
    regions: list[Region],
    profile: PageProfile,
    risk: str = "LOW",
) -> list[RouteDecision]:

    decisions = []

    for region in regions:
        decisions.append(
            route_region(
                region,
                profile,
                risk,
            )
        )

    return decisions