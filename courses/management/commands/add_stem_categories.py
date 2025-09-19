from django.core.management.base import BaseCommand
from courses.models import CourseCategory


class Command(BaseCommand):
    help = 'Add popular STEM categories to the CourseCategory model'

    def handle(self, *args, **options):
        # Popular STEM categories with descriptions
        stem_categories = [
            {
                'name': 'Computer Science',
                'description': 'Programming, algorithms, data structures, software development, and computer systems'
            },
            {
                'name': 'Mathematics',
                'description': 'Algebra, geometry, calculus, statistics, and mathematical problem-solving'
            },
            {
                'name': 'Physics',
                'description': 'Mechanics, thermodynamics, electricity, magnetism, and fundamental physics concepts'
            },
            {
                'name': 'Chemistry',
                'description': 'Organic chemistry, inorganic chemistry, physical chemistry, and laboratory techniques'
            },
            {
                'name': 'Biology',
                'description': 'Cell biology, genetics, ecology, anatomy, and life sciences'
            },
            {
                'name': 'Engineering',
                'description': 'Mechanical, electrical, civil, and aerospace engineering principles and applications'
            },
            {
                'name': 'Robotics',
                'description': 'Robot design, programming, automation, and artificial intelligence applications'
            },
            {
                'name': 'Data Science',
                'description': 'Data analysis, machine learning, statistics, and big data technologies'
            },
            {
                'name': 'Web Development',
                'description': 'Frontend and backend development, web technologies, and full-stack programming'
            },
            {
                'name': 'Mobile Development',
                'description': 'iOS and Android app development, mobile technologies, and cross-platform solutions'
            },
            {
                'name': 'Game Development',
                'description': 'Game design, programming, graphics, and interactive media creation'
            },
            {
                'name': 'Cybersecurity',
                'description': 'Information security, ethical hacking, network security, and digital forensics'
            },
            {
                'name': 'Artificial Intelligence',
                'description': 'Machine learning, neural networks, natural language processing, and AI applications'
            },
            {
                'name': 'Environmental Science',
                'description': 'Climate science, sustainability, ecology, and environmental protection'
            },
            {
                'name': 'Astronomy',
                'description': 'Space science, planetary studies, astrophysics, and celestial observations'
            },
            {
                'name': 'Geology',
                'description': 'Earth sciences, mineralogy, paleontology, and geological processes'
            },
            {
                'name': 'Biotechnology',
                'description': 'Genetic engineering, bioinformatics, medical technology, and life science applications'
            },
            {
                'name': 'Nanotechnology',
                'description': 'Materials science, molecular engineering, and nanoscale technology applications'
            },
            {
                'name': 'Renewable Energy',
                'description': 'Solar, wind, hydroelectric power, and sustainable energy technologies'
            },
            {
                'name': '3D Printing',
                'description': 'Additive manufacturing, 3D modeling, prototyping, and digital fabrication'
            },
            {
                'name': 'Drones & UAVs',
                'description': 'Unmanned aerial vehicles, drone technology, and autonomous systems'
            },
            {
                'name': 'Virtual Reality',
                'description': 'VR development, immersive technologies, and virtual environment creation'
            },
            {
                'name': 'Blockchain',
                'description': 'Cryptocurrency, smart contracts, distributed systems, and decentralized technologies'
            },
            {
                'name': 'Internet of Things (IoT)',
                'description': 'Connected devices, sensors, smart systems, and embedded computing'
            },
            {
                'name': 'Quantum Computing',
                'description': 'Quantum mechanics, quantum algorithms, and next-generation computing technologies'
            }
        ]

        created_count = 0
        updated_count = 0

        for category_data in stem_categories:
            category, created = CourseCategory.objects.get_or_create(
                name=category_data['name'],
                defaults={'description': category_data['description']}
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created category: {category.name}')
                )
            else:
                # Update description if category already exists
                if category.description != category_data['description']:
                    category.description = category_data['description']
                    category.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated category: {category.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.NOTICE(f'Category already exists: {category.name}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary:\n'
                f'Created: {created_count} categories\n'
                f'Updated: {updated_count} categories\n'
                f'Total processed: {len(stem_categories)} categories'
            )
        )
