"""توليد بيانات تجريبية واقعية للنظام (آمن: لا يعمل إن وُجدت بيانات).

الاستخدام::

    python tools/seed.py            # إنشاء البيانات التجريبية
    python tools/seed.py --force    # الحذف وإعادة الإنشاء (يحذف قاعدة البيانات)
"""
from __future__ import annotations

import _bootstrap  # noqa: F401  (تهيئة الترميز والمسار)

import argparse
import random
import sys
from pathlib import Path

from core import bootstrap, config, db
from core.repos import academic as academic_repo
from core.repos import classes as classes_repo
from core.repos import settings as settings_repo
from core.repos import subjects as subjects_repo
from core.repos import users as users_repo
from core.services import (
    classes_service,
    enrollments_service,
    levels_service,
    students_service,
    subjects_service,
    teachers_service,
    terms_service,
    years_service,
    users_service,
)

SEED_ACTOR = {"id": None, "username": "seed", "role": "admin"}

FIRST_NAMES_MALE = ["أحمد", "محمد", "عبدالله", "سعود", "خالد", "عمر", "يوسف", "إبراهيم", "سالم", "فهد", "طلال", "بندر"]
FIRST_NAMES_FEMALE = ["نورة", "سارة", "ريم", "لمى", "هند", "الجوهرة", "منيرة", "أمل", "دانة", "غادة", "شهد", "رزان"]
FAMILIES = ["العتيبي", "القحطاني", "الحربي", "الشمري", "الدوسري", "الغامدي", "المطيري", "الزهراني", "العنزي", "السبيعي"]
SPECIALTIES = ["رياضيات", "لغة عربية", "علوم", "إنجليزي", "حاسب", "دراسات إسلامية", "اجتماعيات", "نشاط"]

LEVELS = ["الابتدائي", "المتوسط", "الثانوي"]
SUBJECTS_BY_LEVEL = {
    "الابتدائي": ["لغتي", "رياضيات", "علوم", "إنجليزي", "تربية إسلامية"],
    "المتوسط": ["لغة عربية", "رياضيات", "علوم", "إنجليزي", "اجتماعيات", "حاسب"],
    "الثانوي": ["كفايات لغوية", "رياضيات", "فيزياء", "كيمياء", "أحياء", "إنجليزي", "حاسب"],
}
CLASS_NAMES = ["أ", "ب", "ج"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="توليد بيانات تجريبية للنظام")
    parser.add_argument("--force", action="store_true", help="حذف قاعدة البيانات الحالية وإعادة الإنشاء")
    parser.add_argument("--students", type=int, default=48, help="عدد الطلاب التجريبيين (افتراضي 48)")
    return parser.parse_args(argv)


def reset_database() -> None:
    path = Path(config.db_path())
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()
    print(f"تم حذف قاعدة البيانات: {path}")


def ensure_users() -> dict[str, int]:
    created = bootstrap.ensure_initial_admin()
    if created:
        print(f"  + مدير النظام: {created['username']} / {created['password']}")
    accounts = {"admin": users_repo.get_by_username("admin")}
    if not users_repo.get_by_username("staff"):
        uid = users_service.create_user(
            "staff", "منى العبدالله", config.ROLE_STAFF, "Emp#2026!ab", must_change=False, actor=SEED_ACTOR
        )
        accounts["staff"] = users_repo.get(uid)
        print("  + شؤون الطلاب: staff / Emp#2026!ab")
    if not users_repo.get_by_username("accountant"):
        uid = users_service.create_user(
            "accountant", "فيصل المالكي", config.ROLE_ACCOUNTANT, "Finance#2026!", must_change=False, actor=SEED_ACTOR
        )
        accounts["accountant"] = users_repo.get(uid)
        print("  + المحاسب: accountant / Finance#2026!")
    return accounts


def seed_academic() -> tuple[int, int]:
    existing_years = academic_repo.list_years()
    year = next((y for y in existing_years if y["name"] == "2026/2027"), None)
    if year:
        year_id = int(year["id"])
    else:
        year_id = years_service.create_year(
            "2026/2027", "2026-08-25", "2027-06-20", True, actor=SEED_ACTOR
        )
    existing_terms = academic_repo.list_terms(year_id)
    term_a = next((t for t in existing_terms if t["name"] == "الفصل الأول"), None)
    if term_a:
        term_id = int(term_a["id"])
    else:
        term_id = terms_service.create_term(
            year_id, "الفصل الأول", "2026-08-25", "2027-01-10", True, actor=SEED_ACTOR
        )
    if not any(t["name"] == "الفصل الثاني" for t in existing_terms):
        terms_service.create_term(
            year_id, "الفصل الثاني", "2027-01-15", "2027-06-20", False, actor=SEED_ACTOR
        )
    print(f"  + السنة الدراسية 2026/2027 والفصلان الدراسيان (الحالي: {term_id})")
    return year_id, term_id


def seed_levels_and_subjects() -> dict[str, int]:
    levels: dict[str, int] = {}
    existing_levels = {lv["name"]: int(lv["id"]) for lv in academic_repo.list_levels()}
    for index, name in enumerate(LEVELS, start=1):
        if name in existing_levels:
            levels[name] = existing_levels[name]
        else:
            levels[name] = levels_service.create_level(name, index * 10, None, actor=SEED_ACTOR)
    for level_name, subject_names in SUBJECTS_BY_LEVEL.items():
        existing_subjects = {s["name"] for s in subjects_repo.list_subjects(levels[level_name])}
        for order, subject_name in enumerate(subject_names, start=1):
            if subject_name in existing_subjects:
                continue
            subjects_service.create_subject(
                subject_name,
                f"{level_name[:3]}-{order:02d}",
                levels[level_name],
                4 if order <= 3 else 2,
                100,
                actor=SEED_ACTOR,
            )
    total = sum(len(items) for items in SUBJECTS_BY_LEVEL.values())
    print(f"  + {len(levels)} مراحل و{total} مادة دراسية")
    return levels


def seed_teachers(count: int = 10) -> list[int]:
    """إنشاء معلمين تجريبيين (أول ثلاثة بحسابات دخول)."""
    teacher_ids: list[int] = []
    for index in range(count):
        name = f"{random.choice(FIRST_NAMES_MALE)} {random.choice(FAMILIES)}"
        user_id = None
        if index < 3:  # ثلاثة معلمين بحسابات دخول لتجربة صلاحية المعلّم
            username = f"teacher{index + 1}"
            if not users_repo.get_by_username(username):
                user_id = users_service.create_user(
                    username, name, config.ROLE_TEACHER, "Faculty#2026!", must_change=False, actor=SEED_ACTOR
                )
        teacher_ids.append(
            teachers_service.create_teacher(
                name,
                str(4000000000 + index),
                f"0555{index:06d}",
                None,
                f"202{index % 5}-09-01",
                SPECIALTIES[index % len(SPECIALTIES)],
                4500 + index * 150,
                user_id=user_id,
                actor=SEED_ACTOR,
            )
        )
    print(f"  + {count} معلماً (منهم 3 بحساب دخول: teacher1..teacher3 / Teach@123)")
    return teacher_ids


def seed_classes(levels: dict[str, int], year_id: int, teacher_ids: list[int]) -> list[int]:
    """إنشاء فصلين لكل مرحلة مع مشرف لكل فصل."""
    class_ids: list[int] = []
    for index, (level_name, level_id) in enumerate(levels.items()):
        for slot, suffix in enumerate(CLASS_NAMES[:2]):
            cname = f"{level_name} - {suffix}"
            existing = classes_repo.get_by_name_and_year(cname, year_id)
            if existing:
                class_ids.append(int(existing["id"]))
                continue
            class_ids.append(
                classes_service.create_class(
                    cname,
                    level_id,
                    year_id,
                    25,
                    f"قاعة {index + 1}{slot + 1}",
                    teacher_ids[(index + slot) % len(teacher_ids)],
                    actor=SEED_ACTOR,
                )
            )
    print(f"  + {len(class_ids)} فصلاً دراسياً بسعة 25 مقعداً")
    return class_ids


def seed_students(count: int, class_ids: list[int], year_id: int) -> int:
    enrolled = 0
    for index in range(count):
        gender = "ذكر" if index % 2 == 0 else "أنثى"
        first = random.choice(FIRST_NAMES_MALE if gender == "ذكر" else FIRST_NAMES_FEMALE)
        full_name = f"{first} {random.choice(FAMILIES)}"
        student_id = students_service.create_student(
            {
                "full_name": full_name,
                "national_id": str(1000000000 + index),
                "gender": gender,
                "birth_date": f"20{10 + (index % 6):02d}-0{(index % 9) + 1}-1{index % 9}",
                "guardian_name": f"{random.choice(FIRST_NAMES_MALE)} {random.choice(FAMILIES)}",
                "guardian_phone": f"0556{index:06d}",
                "address": f"حي النموذجي - شارع {index % 20 + 1}",
                "status": "منتظم",
            },
            year_name="2026",
            actor=SEED_ACTOR,
        )
        target_class = class_ids[index % len(class_ids)]
        try:
            enrollments_service.enroll(
                student_id, target_class, year_id=year_id, actor=SEED_ACTOR
            )
            enrolled += 1
        except Exception as exc:  # الفصل ممتلئ → ننتقل للتالي
            for candidate in class_ids:
                try:
                    enrollments_service.enroll(
                        student_id, candidate, year_id=year_id, actor=SEED_ACTOR
                    )
                    enrolled += 1
                    break
                except Exception:
                    continue
            else:  # pragma: no cover - لا يحدث مع الأحجام الافتراضية
                print(f"    ! لم يتم تسجيل الطالب {student_id}: {exc}")
    print(f"  + {count} طالباً و{enrolled} تسجيلاً فعّالاً")
    return enrolled


def seed_assignments(class_ids: list[int], teacher_ids: list[int]) -> int:
    total = 0
    all_subjects = subjects_service.list_subjects()
    for index, class_id in enumerate(class_ids):
        klass = classes_service.get_class(class_id)
        level_subjects = [
            subject for subject in all_subjects if subject["level_id"] == klass["level_id"]
        ]
        for slot, subject in enumerate(level_subjects[:4]):
            try:
                teachers_service.create_assignment(
                    teacher_ids[(index + slot) % len(teacher_ids)],
                    subject["id"],
                    class_id,
                    None,
                    actor=SEED_ACTOR,
                )
                total += 1
            except Exception:
                continue
    print(f"  + {total} إسناداً تدريسياً")
    return total


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("=" * 66)
    print("توليد بيانات تجريبية — نظام إدارة المؤسسة التعليمية")
    print("=" * 66)
    if args.force:
        reset_database()
    db.init_db()
    settings_repo.ensure_defaults()

    if students_service.stats()["total"] > 0 and not args.force:
        print("توجد بيانات بالفعل. استخدم --force لإعادة الإنشاء من الصفر.")
    # إذا وُجدت طلاب لكن ينقص إسناد التدريس، أكمل الناقص
    if students_service.stats()["total"] > 0 and not args.force:
        year_id, _term_id = seed_academic()
        teacher_ids = [t["id"] for t in teachers_service.list_teachers()]
        class_ids = [c["id"] for c in classes_service.list_classes(year_id)]
        assignments_count = len(teachers_service.list_assignments())
        if assignments_count == 0 and class_ids and teacher_ids:
            seed_assignments(class_ids, teacher_ids)
            print("اكتمل إسناد المواد للمعلمين.")
            return 0
        print("توجد بيانات بالفعل. استخدم --force لإعادة الإنشاء من الصفر.")
        return 1

        return 1

    ensure_users()
    year_id, _term_id = seed_academic()
    levels = seed_levels_and_subjects()
    teacher_ids = seed_teachers()
    class_ids = seed_classes(levels, year_id, teacher_ids)
    seed_students(args.students, class_ids, year_id)
    seed_assignments(class_ids, teacher_ids)

    print("-" * 66)
    print("اكتمل توليد البيانات بنجاح.")
    print("شغّل النظام:  python app.py")
    print("ثم ادخل على: http://127.0.0.1:8080")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
