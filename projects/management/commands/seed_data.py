import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from projects.models import (
    Category, Tag, Project, ProjectImage, Donation,
    Rating, Comment, ProjectReport, CommentReport
)

User = get_user_model()


def generate_sample_image(text, bg_color=(13, 110, 253), width=800, height=500):
    """Creates a sample PIL image with title text."""
    image = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)
    
    # Draw geometric background accent
    draw.rectangle([0, height - 80, width, height], fill=(15, 23, 42))
    
    # Save to BytesIO
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=85)
    return ContentFile(buffer.getvalue(), name=f"{text.lower().replace(' ', '_')}.jpg")


class Command(BaseCommand):
    help = 'Seeds database with realistic demo Egyptian crowdfunding data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE('Starting database seed for CrowdFund Egypt...'))

        # 1. Create Superuser Admin
        admin_user, created = User.objects.get_or_create(
            email='admin@crowdfundegypt.com',
            defaults={
                'first_name': 'Admin',
                'last_name': 'Manager',
                'mobile_phone': '01000000000',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
                'country': 'Egypt',
            }
        )
        if created:
            admin_user.set_password('Admin123456!')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f'Created Admin: admin@crowdfundegypt.com / Admin123456!'))

        # 2. Create Regular Demo Users
        users_data = [
            {'first_name': 'Ahmed', 'last_name': 'Hassan', 'email': 'ahmed.hassan@example.com', 'mobile_phone': '01012345678', 'city': 'Cairo'},
            {'first_name': 'Sara', 'last_name': 'Ibrahim', 'email': 'sara.ibrahim@example.com', 'mobile_phone': '01123456789', 'city': 'Alexandria'},
            {'first_name': 'Nour', 'last_name': 'Ali', 'email': 'nour.ali@example.com', 'mobile_phone': '01234567890', 'city': 'Giza'},
            {'first_name': 'Tarek', 'last_name': 'Mahmoud', 'email': 'tarek.mahmoud@example.com', 'mobile_phone': '01512345678', 'city': 'Mansoura'},
            {'first_name': 'Mariam', 'last_name': 'Khalil', 'email': 'mariam.khalil@example.com', 'mobile_phone': '01098765432', 'city': 'Aswan'},
        ]

        created_users = []
        for u in users_data:
            user_obj, u_created = User.objects.get_or_create(
                email=u['email'],
                defaults={
                    'first_name': u['first_name'],
                    'last_name': u['last_name'],
                    'mobile_phone': u['mobile_phone'],
                    'country': 'Egypt',
                    'is_active': True,
                    'facebook_profile': f"https://facebook.com/{u['first_name'].lower()}.{u['last_name'].lower()}",
                }
            )
            if u_created:
                user_obj.set_password('Password123!')
                user_obj.save()
            created_users.append(user_obj)

        self.stdout.write(self.style.SUCCESS(f'Created {len(created_users)} active demo users.'))

        # 3. Create Categories
        categories_data = [
            {'name': 'Technology & AI', 'description': 'Software, robotics, artificial intelligence, and hardware innovations in Egypt.'},
            {'name': 'Healthcare & Medical', 'description': 'Medical relief, clinic equipment, and assistive healthcare projects.'},
            {'name': 'Education & Youth', 'description': 'Schools, scholarships, STEM programs, and digital learning for Egyptian students.'},
            {'name': 'Creative Arts & Culture', 'description': 'Independent Egyptian cinema, music, heritage crafts, and literature.'},
            {'name': 'Community & Social Aid', 'description': 'Direct community support, poverty relief, and neighborhood empowerment.'},
            {'name': 'Green Energy & Climate', 'description': 'Solar solutions, recycling, clean agriculture, and ecological preservation.'},
        ]

        created_cats = {}
        for cat in categories_data:
            cat_obj, _ = Category.objects.get_or_create(name=cat['name'], defaults={'description': cat['description']})
            created_cats[cat['name']] = cat_obj

        # 4. Create Tags
        tags_data = ['cairo', 'alexandria', 'tech', 'ai', 'education', 'health', 'solar', 'startup', 'youth', 'fayoum', 'aswan', 'children', 'environment']
        created_tags = {}
        for t in tags_data:
            tag_obj, _ = Tag.objects.get_or_create(name=t)
            created_tags[t] = tag_obj

        # 5. Create Egyptian Projects
        now = timezone.now()
        projects_data = [
            {
                'title': 'Solar-Powered Irrigation for Fayoum Farmers',
                'category': created_cats['Green Energy & Climate'],
                'creator': created_users[0],
                'target': Decimal('350000.00'),
                'details': (
                    "Smallholder farmers in Fayoum face rising diesel fuel costs to run water pumps for agriculture. "
                    "This initiative aims to install 12 communal solar pump stations across 300 acres of fertile farmland, "
                    "reducing carbon emissions, decreasing operational expenses by 70%, and securing sustainable livelihoods for over 80 Egyptian farming families."
                ),
                'is_featured': True,
                'tags': ['solar', 'fayoum', 'environment', 'startup'],
                'color': (34, 197, 94),
            },
            {
                'title': 'AI Diagnostic App for Rural Egyptian Clinics',
                'category': created_cats['Technology & AI'],
                'creator': created_users[1],
                'target': Decimal('220000.00'),
                'details': (
                    "Access to specialized radiology and cardiology consultations is scarce in remote rural health centers across Upper Egypt. "
                    "Our team of Cairo University medical and engineering graduates is developing an offline-capable mobile AI app that assists rural doctors in rapid preliminary X-ray and ECG screenings."
                ),
                'is_featured': True,
                'tags': ['ai', 'tech', 'health', 'cairo'],
                'color': (59, 130, 246),
            },
            {
                'title': 'Digital STEM Labs in 20 Public Egyptian Schools',
                'category': created_cats['Education & Youth'],
                'creator': created_users[2],
                'target': Decimal('180000.00'),
                'details': (
                    "Equipping public elementary school classrooms in Giza and Qalyubia with modern computer tablets, coding kits, and interactive science modules. "
                    "We train local Egyptian teachers and bring engaging robotics curricula to over 4,000 underprivileged children."
                ),
                'is_featured': True,
                'tags': ['education', 'youth', 'children', 'tech'],
                'color': (245, 158, 11),
            },
            {
                'title': 'Reviving Ancient Nubian Handicraft Workshops',
                'category': created_cats['Creative Arts & Culture'],
                'creator': created_users[4],
                'target': Decimal('120000.00'),
                'details': (
                    "Protecting authentic Nubian heritage and architectural art through a dedicated community workshop in Aswan. "
                    "Empowering 60 local women artisans with weaving equipment, natural dying supplies, and global e-commerce training."
                ),
                'is_featured': True,
                'tags': ['aswan', 'youth', 'egypt'],
                'color': (168, 85, 247),
            },
            {
                'title': 'Alexandria Coastline Marine Wildlife Rescue Unit',
                'category': created_cats['Green Energy & Climate'],
                'creator': created_users[3],
                'target': Decimal('150000.00'),
                'details': (
                    "Protecting endangered Mediterranean sea turtles and marine life along the coast of Alexandria. "
                    "Funds will support emergency veterinary triage equipment, beach cleanup patrols, and university research monitoring."
                ),
                'is_featured': False,
                'tags': ['alexandria', 'environment'],
                'color': (14, 165, 233),
            },
            {
                'title': 'Free 3D-Printed Prosthetics for Egyptian Children',
                'category': created_cats['Healthcare & Medical'],
                'creator': created_users[0],
                'target': Decimal('280000.00'),
                'details': (
                    "Providing custom lightweight, functional 3D-printed bionic limbs free of charge to children with upper-limb differences in Egypt. "
                    "Each device costs only a fraction of traditional prosthetics and brings immense joy and independence."
                ),
                'is_featured': True,
                'tags': ['health', 'children', 'tech'],
                'color': (239, 68, 68),
            },
            {
                'title': 'Cairo Downtown Community Kitchen & Meals Program',
                'category': created_cats['Community & Social Aid'],
                'creator': created_users[1],
                'target': Decimal('90000.00'),
                'details': (
                    "A community-driven kitchen preparing 500 hot, nutritious meals daily for vulnerable elderly and homeless residents in Downtown Cairo. "
                    "Partnering with local markets to eliminate food waste."
                ),
                'is_featured': False,
                'tags': ['cairo', 'egypt'],
                'color': (249, 115, 22),
            },
        ]

        created_projects = []
        for pdata in projects_data:
            proj, p_created = Project.objects.get_or_create(
                title=pdata['title'],
                defaults={
                    'category': pdata['category'],
                    'creator': pdata['creator'],
                    'total_target': pdata['target'],
                    'details': pdata['details'],
                    'start_time': now - timezone.timedelta(days=5),
                    'end_time': now + timezone.timedelta(days=45),
                    'status': 'running',
                    'is_featured': pdata['is_featured'],
                }
            )
            if p_created:
                # Add Tags
                for tag_name in pdata['tags']:
                    if tag_name in created_tags:
                        proj.tags.add(created_tags[tag_name])

                # Create 2 sample images for carousel
                img1_file = generate_sample_image(f"{proj.title} 1", bg_color=pdata['color'])
                ProjectImage.objects.create(project=proj, image=img1_file, is_cover=True)

                img2_file = generate_sample_image(f"{proj.title} 2", bg_color=(30, 41, 59))
                ProjectImage.objects.create(project=proj, image=img2_file, is_cover=False)

            created_projects.append(proj)

        self.stdout.write(self.style.SUCCESS(f'Created {len(created_projects)} projects with images and tags.'))

        # 6. Add Demo Donations
        donations_plan = [
            (created_users[1], created_projects[0], Decimal('25000.00')),
            (created_users[2], created_projects[0], Decimal('50000.00')),
            (created_users[3], created_projects[0], Decimal('15000.00')),
            (created_users[0], created_projects[1], Decimal('80000.00')),
            (created_users[4], created_projects[1], Decimal('45000.00')),
            (created_users[1], created_projects[2], Decimal('60000.00')),
            (created_users[3], created_projects[3], Decimal('35000.00')),
            (created_users[2], created_projects[4], Decimal('20000.00')),
            (created_users[1], created_projects[5], Decimal('120000.00')),
            (created_users[4], created_projects[6], Decimal('18000.00')),
        ]
        for donor, project, amount in donations_plan:
            Donation.objects.get_or_create(
                user=donor,
                project=project,
                amount=amount,
                defaults={'created_at': now - timezone.timedelta(days=2)}
            )

        # 7. Add Demo Ratings (5 stars for top projects)
        ratings_plan = [
            (created_users[1], created_projects[0], 5),
            (created_users[2], created_projects[0], 5),
            (created_users[3], created_projects[0], 5),
            (created_users[0], created_projects[1], 5),
            (created_users[4], created_projects[1], 5),
            (created_users[2], created_projects[1], 4),
            (created_users[1], created_projects[2], 5),
            (created_users[3], created_projects[2], 4),
            (created_users[0], created_projects[3], 4),
            (created_users[1], created_projects[5], 5),
            (created_users[2], created_projects[5], 5),
        ]
        for user, project, score in ratings_plan:
            Rating.objects.update_or_create(
                user=user,
                project=project,
                defaults={'score': score}
            )

        # 8. Add Demo Comments & Nested Replies
        for proj in created_projects[:4]:
            c1, _ = Comment.objects.get_or_create(
                user=created_users[1],
                project=proj,
                content="This is an incredible initiative for Egypt! How can local volunteers get involved?"
            )
            # Add reply from creator
            Comment.objects.get_or_create(
                user=proj.creator,
                project=proj,
                parent=c1,
                content="Thank you Sara! We will be hosting community orientation workshops next month. Stay tuned for updates!"
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded complete demo data!'))
        self.stdout.write(self.style.SUCCESS('Admin Login: admin@crowdfundegypt.com | Admin123456!'))
        self.stdout.write(self.style.SUCCESS('Demo User: ahmed.hassan@example.com | Password123!'))
