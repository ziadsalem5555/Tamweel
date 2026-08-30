import os
import glob
import sys
from django.core.management.base import BaseCommand
from django.core.files import File
from projects.models import Project, ProjectImage

class Command(BaseCommand):
    help = 'Links user photos from folder to projects by name order'

    def handle(self, *args, **options):
        desktop = r"C:\Users\LORD laptop\Desktop"
        src_dir = None
        for item in os.listdir(desktop):
            full_path = os.path.join(desktop, item)
            if os.path.isdir(full_path) and ("صور" in item or "photos project" in item.lower()):
                # Check if it has 1.jpg or jpg files
                jpgs = [f for f in os.listdir(full_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                if jpgs:
                    src_dir = full_path
                    break

        if not src_dir:
            self.stdout.write(self.style.ERROR("Could not find photos folder."))
            return

        self.stdout.write("Photos folder located on Desktop.")
        
        # Sort naturally / alphabetically (e.g. 1.jpg, 2.jpg, 3.jpg, 4.jpg, 5.jpg)
        def sort_key(name):
            base = os.path.splitext(name)[0]
            try:
                return (0, int(base))
            except ValueError:
                return (1, name)

        files = sorted(
            [f for f in os.listdir(src_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))],
            key=sort_key
        )

        self.stdout.write(f"Images in order: {len(files)} files found.")

        projects = list(Project.objects.all().order_by('id'))

        for i, filename in enumerate(files):
            if i < len(projects):
                proj = projects[i]
                file_path = os.path.join(src_dir, filename)
                # Set previous images to is_cover=False
                proj.images.all().update(is_cover=False)
                
                with open(file_path, 'rb') as f:
                    django_file = File(f, name=f"project_{proj.id}_{filename}")
                    img_obj = ProjectImage.objects.create(
                        project=proj,
                        image=django_file,
                        is_cover=True
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"Linked [{filename}] -> Project #{proj.id} '{proj.title}'"
                    ))
