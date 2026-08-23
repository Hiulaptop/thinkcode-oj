from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0232_organization_problem_tag'),
    ]

    operations = [
        migrations.AddField(
            model_name='problemdata',
            name='r2_release_key',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='R2 release package key'),
        ),
        migrations.AddField(
            model_name='problemdata',
            name='r2_release_sha256',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='R2 release SHA-256'),
        ),
        migrations.AddField(
            model_name='problemdata',
            name='r2_release_version',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='R2 release version'),
        ),
        migrations.AddField(
            model_name='problemdata',
            name='r2_released_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='R2 released at'),
        ),
    ]
