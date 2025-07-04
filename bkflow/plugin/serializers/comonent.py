# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
# -*- coding: utf-8 -*-

import re
from enum import Enum

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.library import ComponentLibrary
from pipeline.component_framework.models import ComponentModel
from pipeline.exceptions import ComponentNotExistException
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from bkflow.plugin.models import SpacePluginConfig as SpacePluginConfigModel

group_en_pattern = re.compile(r"(?:\()(.*)(?:\))")


class PluginType(Enum):
    UNIFORM_API = "uniform_api"
    COMPONENT = "component"
    BLUEKING = "blueking"


class ComponentModelSerializer(serializers.ModelSerializer):
    output = serializers.SerializerMethodField(read_only=True)
    form = serializers.SerializerMethodField(read_only=True)
    output_form = serializers.SerializerMethodField(read_only=True)
    desc = serializers.SerializerMethodField(read_only=True)
    form_is_embedded = serializers.SerializerMethodField(read_only=True)
    # 国际化
    group_name = serializers.SerializerMethodField(read_only=True)
    group_icon = serializers.SerializerMethodField(read_only=True)
    name = serializers.SerializerMethodField(read_only=True)
    sort_key_group_en = serializers.SerializerMethodField(read_only=True)
    base = serializers.SerializerMethodField(read_only=True)

    def get_output(self, instance):
        return self.component.outputs_format()

    def get_form(self, instance):
        return self.component.form

    def get_output_form(self, instance):
        return self.component.output_form

    def get_desc(self, instance):
        return self.component.desc

    def get_form_is_embedded(self, instance):
        return self.component.form_is_embedded()

    # 国际化
    def get_group_name(self, instance):
        return _(self.component_name[0])

    def get_group_icon(self, instance):
        return self.component.group_icon

    def get_name(self, instance):
        return _(self.component_name[1])

    def get_sort_key_group_en(self, instance):
        group_name_en = group_en_pattern.findall(self.component_name[0] or "")
        return group_name_en[0] if group_name_en else "#"

    def get_base(self, instance):
        return getattr(self.component, "base", None)

    class Meta:
        model = ComponentModel
        exclude = ["status", "id"]

    def to_representation(self, instance):
        try:
            self.component = ComponentLibrary.get_component_class(instance.code, instance.version)
            self.component_name = instance.name.split("-")
        except ComponentNotExistException:
            raise NotFound("Can not found {}({})".format(instance.code, instance.version))
        return super(ComponentModelSerializer, self).to_representation(instance)


class ComponentModelListSerializer(ComponentModelSerializer):
    base = None


class ComponentListQuerySerializer(serializers.Serializer):
    space_id = serializers.CharField(help_text="空间ID")
    scope_type = serializers.CharField(help_text="空间下scope类型", required=False)
    scope_id = serializers.CharField(help_text="空间下scope ID", required=False)


class ComponentDetailQuerySerializer(serializers.Serializer):
    space_id = serializers.CharField(help_text="空间ID")

    def validate_space_id(self, space_id):
        plugin_code = self.context["plugin_code"]
        space_allow_list = SpacePluginConfigModel.objects.get_space_allow_list(space_id)
        if plugin_code in settings.SPACE_PLUGIN_LIST and plugin_code not in space_allow_list:
            raise serializers.ValidationError(_("插件 {} 不在空间 {} 的插件白名单中").format(plugin_code, space_id))
        return space_id


class ComponentModelDetailSerializer(ComponentModelSerializer):
    phase = None
    sort_key_group_en = None


# 抽象基类，用于定义公有字段
class BasePluginSerializer(serializers.Serializer):
    plugin_code = serializers.CharField(help_text="Plugin code", required=True)


class UniformAPISerializer(BasePluginSerializer):
    # API 插件类型字段
    meta_url = serializers.CharField(help_text="Meta URL", required=True)


class ComponentSerializer(BasePluginSerializer):
    pass  # 特定于内置插件类型的字段


class BlueKingSerializer(BasePluginSerializer):
    pass  # 特定于蓝鲸插件类型的字段


# 主序列化器
class UniformPluginSerializer(serializers.Serializer):
    space_id = serializers.CharField(help_text="空间ID", required=True)
    template_id = serializers.CharField(help_text="Template ID", required=True)

    uniform_api = serializers.ListField(child=UniformAPISerializer(), required=False)
    component = serializers.ListField(child=ComponentSerializer(), required=False)
    blueking = serializers.ListField(child=BlueKingSerializer(), required=False)

    target_fields = serializers.ListField(child=serializers.CharField(), help_text="目标字段列表", required=False)

    def validate(self, data):
        # 确保至少一个插件类型有处理的数据
        if not any([data.get("uniform_api"), data.get("component"), data.get("blueking")]):
            raise serializers.ValidationError(
                "At least one plugin_type list (uniform_api, component, blueking) must be provided."
            )

        # 可以添加其他的验证逻辑
        return data
