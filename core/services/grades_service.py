"""خدمة إدارة التقييمات ورصد الدرجات والنتائج الأكاديمية."""
from __future__ import annotations

from typing import Any

from core.exceptions import NotFoundError, ValidationError
from core.repos import audit
from core.repos import classes as classes_repo
from core.repos import grades as grades_repo
from core.repos import subjects as subjects_repo


def create_assessment(
    name: str,
    subject_id: int,
    class_id: int,
    term_id: int,
    max_score: float,
    weight: float = 100.0,
    assessment_date: str | None = None,
    actor: dict[str, Any] | None = None,
) -> int:
    clean_name = str(name).strip()
    if not clean_name:
        raise ValidationError("اسم التقييم مطلوب")
    if max_score <= 0:
        raise ValidationError("الدرجة العظمى يجب أن تكون أكبر من الصفر")
    if weight <= 0:
        raise ValidationError("وزن التقييم يجب أن يكون أكبر من الصفر")

    subject = subjects_repo.get(subject_id)
    if not subject:
        raise NotFoundError("المادة الدراسية غير موجودة")
    klass = classes_repo.get(class_id)
    if not klass:
        raise NotFoundError("الفصل الدراسي غير موجود")

    user_id = actor.get("id") if actor else None
    assessment_id = grades_repo.create_assessment(
        name=clean_name,
        subject_id=subject_id,
        class_id=class_id,
        term_id=term_id,
        max_score=max_score,
        weight=weight,
        assessment_date=assessment_date,
        created_by=user_id,
    )
    audit.log(
        "إنشاء تقييم",
        entity="assessments",
        entity_id=assessment_id,
        details=f"إنشاء تقييم '{clean_name}' لمادة {subject['name']} فصل {klass['name']}",
        user=actor,
    )
    return assessment_id


def save_student_grade(
    assessment_id: int,
    student_id: int,
    score: float,
    notes: str | None = None,
    actor: dict[str, Any] | None = None,
) -> int:
    assessment = grades_repo.get_assessment(assessment_id)
    if not assessment:
        raise NotFoundError("التقييم غير موجود")

    if score < 0 or score > assessment["max_score"]:
        raise ValidationError(f"الدرجة يجب أن تكون بين 0 و {assessment['max_score']}")

    user_id = actor.get("id") if actor else None
    grade_id = grades_repo.save_grade(
        assessment_id=assessment_id,
        student_id=student_id,
        score=score,
        notes=notes,
        recorded_by=user_id,
    )
    return grade_id


def bulk_save_grades(
    assessment_id: int,
    grades_dict: dict[int, float],
    actor: dict[str, Any] | None = None,
) -> int:
    """حفظ درجات مجموعة طلاب دفعة واحدة."""
    saved = 0
    for student_id, score in grades_dict.items():
        if score is not None:
            save_student_grade(assessment_id, student_id, float(score), actor=actor)
            saved += 1
    return saved


def student_final_results(student_id: int, term_id: int | None = None) -> dict[str, Any]:
    """حساب النسب التقديرية لكل مادة ووضع جداول النتائج النهائية."""
    rows = grades_repo.student_subject_grades(student_id, term_id=term_id)
    subjects: dict[str, dict[str, Any]] = {}
    for g in rows:
        sub = g["subject_name"]
        if sub not in subjects:
            subjects[sub] = {"total_weight": 0.0, "weighted_score": 0.0, "grades": []}
        w = float(g.get("weight") or 0) / 100.0
        norm = float(g["score"]) / (g["max_score"] or 100) * 100.0
        subjects[sub]["total_weight"] += float(g.get("weight") or 0)
        subjects[sub]["weighted_score"] += norm * w
        subjects[sub]["grades"].append(g)

    results = []
    total_w, total_ws = 0.0, 0.0
    for sub_name, sub in subjects.items():
        if sub["total_weight"] > 0:
            avg = sub["weighted_score"] / (sub["total_weight"] / 100.0) if sub["total_weight"] else 0
            grade_letter = _letter_grade(avg)
            results.append({"subject": sub_name, "average": round(avg, 2), "letter": grade_letter})
            total_w += 1
            total_ws += avg

    overall = round(total_ws / total_w, 2) if total_w else 0.0
    return {"subjects": results, "overall_average": overall, "overall_letter": _letter_grade(overall)}


def _letter_grade(avg: float) -> str:
    if avg >= 90:
        return "ممتاز"
    if avg >= 80:
        return "جيد جداً"
    if avg >= 65:
        return "جيد"
    if avg >= 50:
        return "مقبول"
    return "راسب"


def delete_assessment(assessment_id: int, actor: dict[str, Any] | None = None) -> None:
    assessment = grades_repo.get_assessment(assessment_id)
    if not assessment:
        raise NotFoundError("التقييم غير موجود")
    grades_repo.delete_assessment(assessment_id)
    audit.log(
        "حذف تقييم",
        entity="assessments",
        entity_id=assessment_id,
        details=f"حذف تقييم '{assessment['name']}'",
        user=actor,
    )

