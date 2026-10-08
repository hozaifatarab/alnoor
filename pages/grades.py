"""شاشة الدرجات: إنشاء التقييمات، رصد الدرجات، والنتائج النهائية."""
from __future__ import annotations

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons
from pywebio.session import go_app

from core import auth
from core.repos import grades as grades_repo
from core.services import classes_service, grades_service
from ui import charts, components, layout, options

APP = "grades"


def grades() -> None:
    """شاشة التقييمات والدرجات."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="الدرجات والتقييمات")

    with components.error_boundary("الدرجات"):
        class_options = options.classes()
        if not class_options:
            layout.alert("لا توجد فصول معرّفة بعد.", "warn")
            go_app("classes", new_window=False)
            return

        data = input_group(
            "اختيار الفصل",
            [select("الفصل *", name="class_id", options=class_options, required=True)],
            cancelable=False,
        )
        class_id = int(data["class_id"])
        _render_assessments(class_id)
        put_buttons(
            [
                {"label": "➕ تقييم جديد", "value": "add", "color": "primary"},
                {"label": "📝 رصد/تعديل درجات", "value": "enter", "color": "secondary"},
                {"label": "🏅 النتائج النهائية", "value": "results", "color": "secondary"},
                {"label": "🗑 حذف تقييم", "value": "delete", "color": "danger"},
            ],
            onclick=lambda value: _handle(value, class_id),
            small=True,
        )
        layout.footer()


def _render_assessments(class_id: int) -> None:
    rows = grades_repo.list_assessments(class_id=class_id)
    klass = classes_service.get_class(class_id)
    layout.section(f"تقييمات {klass['name'] if klass else ''}", f"عدد التقييمات: {len(rows)}")
    components.table(
        ["التقييم", "المادة", "الدرجة العظمى", "الوزن", "التاريخ", "عدد المرصود"],
        [
            [
                row["name"],
                row["subject_name"],
                row["max_score"],
                row["weight"],
                row.get("assessment_date") or "—",
                row.get("graded_count") or 0,
            ]
            for row in rows
        ],
        empty_message="لا توجد تقييمات لهذا الفصل بعد",
    )


def _handle(value: str, class_id: int) -> None:
    if value == "add":
        _create_assessment(class_id)
    elif value == "enter":
        _enter_grades(class_id)
    elif value == "results":
        _render_results(class_id)
    elif value == "delete":
        _delete_assessment(class_id)



def _create_assessment(class_id: int) -> None:
    from core.services import terms_service

    subject_options = options.subjects()
    if not subject_options:
        components.toast_error("لا توجد مواد دراسية — أضف المواد أولاً")
        return
    term = terms_service.current_term()
    data = components.form_modal(
        "إنشاء تقييم جديد",
        [
            input("اسم التقييم *", name="name", required=True, placeholder="مثال: اختبار دوري 1"),
            select("المادة *", name="subject_id", options=subject_options, required=True),
            select(
                "الفصل الدراسي *",
                name="term_id",
                options=options.terms(),
                value=str(term["id"]) if term else None,
                required=True,
            ),
            input("الدرجة العظمى *", name="max_score", value="100", required=True),
            input("الوزن (%)", name="weight", value="100", required=False),
            input("تاريخ التقييم", name="assessment_date", value="", required=False),
        ],
        size="large",
    )
    if not data:
        return
    with components.error_boundary("إنشاء تقييم"):
        grades_service.create_assessment(
            data["name"],
            int(data["subject_id"]),
            class_id,
            int(data["term_id"]),
            float(str(data["max_score"]).strip() or 100),
            float(str(data.get("weight") or 100).strip() or 100),
            (data.get("assessment_date") or "").strip() or None,
            actor=auth.current_user(),
        )
        components.toast_ok("تم إنشاء التقييم")
        go_app(APP, new_window=False)


def _enter_grades(class_id: int) -> None:
    rows = grades_repo.list_assessments(class_id=class_id)
    if not rows:
        components.toast_error("لا توجد تقييمات — أنشئ تقييماً أولاً")
        return
    data = components.form_modal(
        "رصد / تعديل الدرجات",
        [
            select(
                "التقييم *",
                name="assessment_id",
                options=[
                    {
                        "label": f"{row['name']} — {row['subject_name']} (من {row['max_score']})",
                        "value": str(row["id"]),
                    }
                    for row in rows
                ],
                required=True,
            )
        ],
    )
    if not data:
        return
    assessment_id = int(data["assessment_id"])
    assessment = grades_repo.get_assessment(assessment_id)
    students = grades_repo.list_assessment_grades(assessment_id, class_id)
    layout.section(
        f"رصد درجات: {assessment['name']}",
        f"المادة: {assessment['subject_name']} — الدرجة العظمى {assessment['max_score']}",
    )
    components.table(
        ["#", "الطالب", "الرقم", "الدرجة الحالية"],
        [
            [
                index,
                row["full_name"],
                row["student_no"],
                row.get("score") if row.get("score") is not None else "— لم تُرصد —",
            ]
            for index, row in enumerate(students, start=1)
        ],
        empty_message="لا يوجد طلاب في هذا الفصل",
    )
    put_buttons(
        [
            {"label": "✏ رصد درجة طالب", "value": "one", "color": "primary"},
            {"label": "⚡ رصد جماعي (كل الطلاب)", "value": "many", "color": "secondary"},
        ],
        onclick=lambda value: _grade_entry_dialog(value, assessment_id, class_id),
        small=True,
    )


def _grade_entry_dialog(value: str, assessment_id: int, class_id: int) -> None:
    """رصد درجة (أو درجات) لتقييم محدد مع التحقق من الحدود."""
    assessment = grades_repo.get_assessment(assessment_id)
    students = grades_repo.list_assessment_grades(assessment_id, class_id)
    if not students:
        components.toast_error("لا يوجد طلاب في هذا الفصل")
        return

    if value == "one":
        data = components.form_modal(
            f"رصد درجة — {assessment['name']}",
            [
                select(
                    "الطالب *",
                    name="student_id",
                    options=[
                        {
                            "label": f"{row['student_no']} — {row['full_name']}",
                            "value": str(row["student_id"]),
                        }
                        for row in students
                    ],
                    required=True,
                ),
                input(
                    f"الدرجة (من {assessment['max_score']}) *",
                    name="score",
                    type="number",
                    required=True,
                ),
                input("ملاحظات", name="notes", required=False),
            ],
        )
        if not data:
            return
        with components.error_boundary("رصد درجة"):
            grades_service.save_student_grade(
                assessment_id,
                int(data["student_id"]),
                float(data["score"]),
                data.get("notes"),
                actor=auth.current_user(),
            )
            components.toast_ok("تم رصد الدرجة")
            go_app(APP, new_window=False)
        return

    _bulk_grade_dialog(assessment, students)


def _bulk_grade_dialog(assessment: dict, students: list[dict]) -> None:
    """رصد جماعي: حقل درجة لكل طالب في نموذج واحد."""
    fields = [
        input(
            f"{row['student_no']} — {row['full_name']}"
            f"{' [' + str(row['score']) + ']' if row.get('score') is not None else ''}",
            name=f"score_{row['student_id']}",
            type="number",
            required=False,
            help_text=f"من {assessment['max_score']}",
        )
        for row in students
    ]
    data = components.form_modal(
        f"رصد جماعي — {assessment['name']}",
        fields,
        size="large",
        help_text="اترك الحقل فارغاً للطلاب غير المرصودين",
    )
    if not data:
        return
    payload: dict[int, float] = {}
    for row in students:
        raw = str(data.get(f"score_{row['student_id']}") or "").strip()
        if raw == "":
            continue
        payload[int(row["student_id"])] = float(raw)
    if not payload:
        components.toast_warn("لم تُدخل أي درجة")
        return
    with components.error_boundary("رصد جماعي"):
        count = grades_service.bulk_save_grades(
            assessment_id=assessment["id"], grades_dict=payload, actor=auth.current_user()
        )
        components.toast_ok(f"تم حفظ {count} درجة")
        go_app(APP, new_window=False)


def _render_results(class_id: int) -> None:
    """النتائج النهائية لطلاب الفصل (متوسطات المواد + التقدير)."""
    roster = classes_service.roster(class_id)
    if not roster:
        components.toast_error("لا يوجد طلاب في هذا الفصل")
        return
    layout.section("النتائج النهائية", "المعدل لكل مادة والتقدير العام (حسب أوزان التقييمات)")
    rows = []
    for student in roster:
        result = grades_service.student_final_results(int(student["id"]))
        rows.append(
            [
                student["student_no"],
                student["full_name"],
                result["overall_average"],
                components.chip(result["overall_letter"], _letter_kind(result["overall_letter"])),
                " — ".join(f"{item['subject']}: {item['average']}" for item in result["subjects"])
                or "— لا توجد درجات —",
            ]
        )
    components.table(
        ["الرقم", "الطالب", "المعدل العام", "التقدير", "المعدلات بحسب المادة"],
        rows,
        empty_message="لا توجد بيانات",
    )
    graded = [row for row in rows if row[2]]
    if graded:
        charts.bar_chart(
            "توزيع المعدلات العامة",
            [(str(row[1])[:18], float(row[2])) for row in graded],
            total=100,
        )


def _letter_kind(letter: str) -> str:
    if letter in ("ممتاز", "جيد جداً"):
        return "ok"
    if letter in ("جيد", "مقبول"):
        return "warn"
    return "bad"


def _delete_assessment(class_id: int) -> None:
    rows = grades_repo.list_assessments(class_id=class_id)
    if not rows:
        components.toast_error("لا توجد تقييمات")
        return
    data = components.form_modal(
        "حذف تقييم",
        [
            select(
                "التقييم *",
                name="assessment_id",
                options=[
                    {"label": f"{row['name']} — {row['subject_name']}", "value": str(row["id"])}
                    for row in rows
                ],
                required=True,
            )
        ],
    )
    if not data:
        return
    if not components.confirm("سيتم حذف التقييم وكل درجاته. متابعة؟", "حذف", "إلغاء"):
        return
    with components.error_boundary("حذف تقييم"):
        grades_service.delete_assessment(int(data["assessment_id"]), actor=auth.current_user())
        components.toast_ok("تم حذف التقييم")
        go_app(APP, new_window=False)

