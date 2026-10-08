# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from powercontext.builtin.artifacts.search import RecallChannelWeights
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import BuiltinConfig, RuntimeConfig, composition
from powercontext.server.settings import ServerSettings


def test_recall_channel_weights_default_to_the_historical_equal_ratio() -> None:
    config = RuntimeConfig()

    assert config.recall_fts_weight == 1.0
    assert config.recall_vector_weight == 1.0
    assert config.recall_channel_weights.fts == 1.0
    assert config.recall_channel_weights.vector == 1.0


def test_recall_channel_weights_are_normalized_as_a_relative_ratio() -> None:
    weights = RuntimeConfig(recall_fts_weight=3.0, recall_vector_weight=1.0).recall_channel_weights
    scaled = RuntimeConfig(recall_fts_weight=300.0, recall_vector_weight=100.0).recall_channel_weights

    assert weights.fts == pytest.approx(1.5)
    assert weights.vector == pytest.approx(0.5)
    assert scaled == weights


def test_recall_channel_weights_support_the_reverse_ratio() -> None:
    weights = RuntimeConfig(recall_fts_weight=1.0, recall_vector_weight=3.0).recall_channel_weights

    assert weights.fts == pytest.approx(0.5)
    assert weights.vector == pytest.approx(1.5)


def test_recall_channel_weights_normalize_finite_subnormal_values() -> None:
    weights = RuntimeConfig(recall_fts_weight=1e-310, recall_vector_weight=1e-310).recall_channel_weights

    assert math.isfinite(weights.fts)
    assert math.isfinite(weights.vector)
    assert weights.fts == pytest.approx(1.0)
    assert weights.vector == pytest.approx(1.0)


def test_recall_channel_weight_total_overflow_reports_the_actual_cause() -> None:
    with pytest.raises(ValueError, match="weight total must be finite"):
        RecallChannelWeights(fts=1e308, vector=1e308)

    with pytest.raises(ValidationError, match="weight total must be finite"):
        RuntimeConfig(recall_fts_weight=1e308, recall_vector_weight=1e308)


def test_composition_passes_recall_weights_to_regular_and_topic_worker_contexts(
    tmp_path: Path,
) -> None:
    runtime_config = RuntimeConfig(recall_fts_weight=1.0, recall_vector_weight=3.0)
    config = BuiltinConfig(
        database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'recall-weights.db'}"),
        runtime=runtime_config,
    )
    expected = runtime_config.recall_channel_weights

    async def scenario() -> None:
        async with composition.open_builtin_contexts(config) as contexts:
            assert contexts.repositories.topic_memories.recall_channel_weights == expected
        async with composition.open_builtin_contexts(config, _topic_memory_worker=True) as worker_contexts:
            assert worker_contexts.repositories.topic_memories.recall_channel_weights == expected

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("fts", "vector"),
    [
        (-1.0, 1.0),
        (1.0, -1.0),
        (math.nan, 1.0),
        (math.inf, 1.0),
        (-math.inf, 1.0),
        (1.0, math.nan),
        (1.0, math.inf),
        (1.0, -math.inf),
        (0.0, 0.0),
        (1e308, 1e308),
        (True, 1.0),
        (1.0, False),
    ],
)
def test_invalid_recall_channel_weights_are_rejected_at_configuration_time(fts: object, vector: object) -> None:
    with pytest.raises(ValidationError):
        RuntimeConfig.model_validate({"recall_fts_weight": fts, "recall_vector_weight": vector})


def test_recall_channel_weights_load_from_the_server_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POWERCONTEXT_SERVER_RUNTIME_RECALL_FTS_WEIGHT", "3")
    monkeypatch.setenv("POWERCONTEXT_SERVER_RUNTIME_RECALL_VECTOR_WEIGHT", "1")

    runtime = ServerSettings().runtime

    assert runtime.recall_fts_weight == 3.0
    assert runtime.recall_vector_weight == 1.0
    assert runtime.recall_channel_weights.fts == pytest.approx(1.5)
    assert runtime.recall_channel_weights.vector == pytest.approx(0.5)
