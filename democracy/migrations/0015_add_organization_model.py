# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-05-19 08:11
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('democracy', '0014_non_editable_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='time of creation')),
                ('modified_at', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='time of last modification')),
                ('published', models.BooleanField(db_index=True, default=True, verbose_name='public')),
                ('deleted', models.BooleanField(db_index=True, default=False, editable=False, verbose_name='deleted')),
                ('id', models.CharField(editable=False, max_length=32, primary_key=True, serialize=False, verbose_name='identifier')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='name')),
                ('admin_users', models.ManyToManyField(blank=True, related_name='admin_organizations', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='organization_created', to=settings.AUTH_USER_MODEL, verbose_name='created by')),
                ('modified_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='organization_modified', to=settings.AUTH_USER_MODEL, verbose_name='last modified by')),
            ],
            options={
                'verbose_name': 'organization',
                'verbose_name_plural': 'organizations',
            },
        ),
        migrations.AddField(
            model_name='hearing',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='hearings', to='democracy.Organization', verbose_name='organization'),
        ),
    ]
