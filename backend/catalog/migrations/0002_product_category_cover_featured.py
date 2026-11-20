from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.RenameField(model_name="product", old_name="cover_url", new_name="cover"),
        migrations.AlterField(
            model_name="product",
            name="cover",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="product",
            name="category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("keyboard", "键盘"),
                    ("mouse", "鼠标"),
                    ("headset", "耳机"),
                    ("monitor", "显示器"),
                    ("stand", "支架"),
                    ("dock", "扩展坞"),
                ],
                default="",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),
    ]
