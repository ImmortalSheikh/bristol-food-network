from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_recurringorder_recurringorderitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='recurring_order',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='generated_orders',
                to='core.recurringorder',
                verbose_name='Generated from recurring template',
            ),
        ),
    ]
