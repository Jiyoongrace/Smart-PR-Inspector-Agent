"""
SKILL.md 파서 및 스킬 레지스트리
SKILL.md를 파싱하여 각 노드에 스킬 메타데이터를 제공합니다.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SKILL_MD_PATH = Path(__file__).parent.parent / "SKILL.md"


@dataclass
class SkillDefinition:
    """SKILL.md에서 파싱된 스킬 정의"""
    id: str
    name: str
    description: str
    trigger: str = ""
    tools: List[str] = field(default_factory=list)
    input_fields: str = ""
    output_fields: str = ""
    model: str = "none"
    prompt: str = ""
    parallel_group: str = ""
    hitl: bool = False
    hitl_actions: List[str] = field(default_factory=list)
    retry: bool = False
    max_retries: int = 0
    retry_node: str = ""
    skip_condition: str = ""
    timeout: str = ""
    rag: Dict[str, str] = field(default_factory=dict)
    checks: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)


@dataclass
class WorkflowDefinition:
    """SKILL.md에서 파싱된 워크플로우 정의"""
    entry: str = ""
    parallel: List[str] = field(default_factory=list)
    join_then: str = ""
    sequence: List[str] = field(default_factory=list)
    end: str = ""
    models: Dict[str, str] = field(default_factory=dict)


class SkillRegistry:
    """
    SKILL.md 기반 스킬 레지스트리

    사용법:
        registry = SkillRegistry.load()
        skill = registry.get_skill("convention")
        print(skill.description)
        print(skill.prompt)

        # 모델 선택
        model = registry.get_model_for_skill("convention")

        # 워크플로우 정보
        workflow = registry.workflow
        print(workflow.parallel)  # ["convention", "test_gen"]
    """

    def __init__(self):
        self.skills: Dict[str, SkillDefinition] = {}
        self.workflow: WorkflowDefinition = WorkflowDefinition()

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "SkillRegistry":
        """SKILL.md 파일을 파싱하여 레지스트리 생성"""
        registry = cls()
        skill_path = path or SKILL_MD_PATH

        if not skill_path.exists():
            logger.warning(f"SKILL.md를 찾을 수 없습니다: {skill_path}")
            return registry

        content = skill_path.read_text(encoding="utf-8")
        registry._parse(content)
        logger.info(
            f"SKILL.md 로드 완료: {len(registry.skills)}개 스킬, "
            f"워크플로우 entry={registry.workflow.entry}"
        )
        return registry

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        """스킬 ID로 정의 조회"""
        return self.skills.get(skill_id)

    def get_model_for_skill(self, skill_id: str) -> Optional[str]:
        """스킬에 적합한 LLM 모델 이름 반환"""
        skill = self.get_skill(skill_id)
        if not skill or skill.model == "none":
            return None
        return self.workflow.models.get(skill.model, skill.model)

    def get_prompt_name(self, skill_id: str) -> Optional[str]:
        """스킬에 연결된 프롬프트 템플릿 이름 반환"""
        skill = self.get_skill(skill_id)
        if skill and skill.prompt:
            return skill.prompt
        return None

    def get_parallel_skills(self) -> List[str]:
        """병렬 실행할 스킬 ID 목록"""
        return self.workflow.parallel

    def get_hitl_skills(self) -> List[SkillDefinition]:
        """HITL이 필요한 스킬 목록"""
        return [s for s in self.skills.values() if s.hitl]

    def get_retryable_skills(self) -> List[SkillDefinition]:
        """재시도 가능한 스킬 목록"""
        return [s for s in self.skills.values() if s.retry]

    def get_rag_config(self, skill_id: str) -> Dict[str, str]:
        """스킬의 RAG 설정 반환"""
        skill = self.get_skill(skill_id)
        if skill:
            return skill.rag
        return {}

    def list_skills(self) -> List[Dict[str, str]]:
        """전체 스킬 목록 (요약)"""
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "model": s.model,
                "hitl": s.hitl,
                "retry": s.retry,
            }
            for s in self.skills.values()
        ]

    def _parse(self, content: str) -> None:
        """SKILL.md 마크다운 파싱"""
        # ## skills 섹션과 ## workflow 섹션 분리
        skills_section = ""
        workflow_section = ""

        sections = re.split(r"^## ", content, flags=re.MULTILINE)
        for section in sections:
            if section.startswith("skills"):
                skills_section = section
            elif section.startswith("workflow"):
                workflow_section = section

        if skills_section:
            self._parse_skills(skills_section)
        if workflow_section:
            self._parse_workflow(workflow_section)

    def _parse_skills(self, section: str) -> None:
        """### 스킬명 블록 파싱"""
        skill_blocks = re.split(r"^### ", section, flags=re.MULTILINE)

        for block in skill_blocks:
            if not block.strip() or block.startswith("skills"):
                continue

            lines = block.strip().split("\n")
            skill_name = lines[0].strip()

            props = {}
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("- ") and ": " in line:
                    key, value = line[2:].split(": ", 1)
                    props[key.strip()] = value.strip()
                elif line.startswith("  - ") and ": " in line:
                    # 중첩 속성 (rag 하위)
                    key, value = line[4:].split(": ", 1)
                    if "rag" not in props:
                        props["rag"] = {}
                    if isinstance(props.get("rag"), dict):
                        props["rag"][key.strip()] = value.strip()

            skill_id = props.get("id", skill_name.lower().replace(" ", "_"))

            # 리스트 파싱 헬퍼
            def parse_list(val: str) -> List[str]:
                if val.startswith("[") and val.endswith("]"):
                    return [
                        item.strip().strip("'\"")
                        for item in val[1:-1].split(",")
                        if item.strip()
                    ]
                return [val]

            skill = SkillDefinition(
                id=skill_id,
                name=skill_name,
                description=props.get("description", ""),
                trigger=props.get("trigger", ""),
                tools=parse_list(props.get("tools", "[]")),
                input_fields=props.get("input", ""),
                output_fields=props.get("output", ""),
                model=props.get("model", "none"),
                prompt=props.get("prompt", ""),
                parallel_group=props.get("parallel_group", ""),
                hitl=props.get("hitl", "").lower() == "true",
                hitl_actions=parse_list(props.get("hitl_actions", "[]")),
                retry=props.get("retry", "").lower() == "true",
                max_retries=int(props.get("max_retries", "0")),
                retry_node=props.get("retry_node", ""),
                skip_condition=props.get("skip_condition", ""),
                timeout=props.get("timeout", ""),
                rag=props.get("rag", {}) if isinstance(props.get("rag"), dict) else {},
                checks=parse_list(props.get("checks", "[]")),
                actions=parse_list(props.get("actions", "[]")),
            )
            self.skills[skill_id] = skill

    def _parse_workflow(self, section: str) -> None:
        """워크플로우 섹션 파싱"""
        lines = section.strip().split("\n")

        def parse_list(val: str) -> List[str]:
            if val.startswith("[") and val.endswith("]"):
                return [
                    item.strip().strip("'\"")
                    for item in val[1:-1].split(",")
                    if item.strip()
                ]
            return [val]

        current_subsection = ""
        for line in lines:
            line = line.strip()
            if line.startswith("### "):
                current_subsection = line[4:].strip()
                continue

            if current_subsection == "execution_order" and line.startswith("- "):
                key_val = line[2:]
                if ": " in key_val:
                    key, val = key_val.split(": ", 1)
                    key = key.strip()
                    val = val.strip()
                    if key == "entry":
                        self.workflow.entry = val
                    elif key == "parallel":
                        self.workflow.parallel = parse_list(val)
                    elif key == "join_then":
                        self.workflow.join_then = val
                    elif key == "sequence":
                        self.workflow.sequence = parse_list(val)
                    elif key == "end":
                        self.workflow.end = val

            elif current_subsection == "models" and line.startswith("- "):
                key_val = line[2:]
                if ": " in key_val:
                    key, val = key_val.split(": ", 1)
                    self.workflow.models[key.strip()] = val.strip()


# ── 전역 싱글턴 ──────────────────────────────────────────────────

_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """전역 스킬 레지스트리 반환 (싱글턴)"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry.load()
    return _registry
