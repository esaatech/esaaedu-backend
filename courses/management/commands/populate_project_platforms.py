"""
Management command to populate initial ProjectPlatform data
This command creates a comprehensive set of project platforms for different age groups and skill levels
"""

from django.core.management.base import BaseCommand
from courses.models import ProjectPlatform


class Command(BaseCommand):
    help = 'Populate initial ProjectPlatform data with popular development platforms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing platforms before adding new ones',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing platforms...')
            ProjectPlatform.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing platforms cleared.'))

        platforms_data = [
            # Visual Programming Platforms
            {
                'name': 'scratch',
                'display_name': 'Scratch Programming Platform',
                'description': 'Visual programming language and online community where children can program and share interactive media such as stories, games, and animation with people from all over the world.',
                'platform_type': 'Visual Programming',
                'base_url': 'https://scratch.mit.edu',
                'api_endpoint': 'https://api.scratch.mit.edu',
                'supported_languages': ['Scratch'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': False,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    'max_projects_per_user': 100,
                    'project_templates': ['game', 'animation', 'story', 'music'],
                    'sharing_enabled': True,
                    'age_restriction': '8+',
                    'tutorials_available': True,
                    'community_features': True
                },
                'icon': 'scratch',
                'color': '#4C97FF',
                'logo_url': 'https://scratch.mit.edu/images/scratch-logo.png',
                'min_age': 8,
                'max_age': 16,
                'skill_levels': ['beginner', 'intermediate'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'scratchjr',
                'display_name': 'ScratchJr',
                'description': 'Introductory programming language that enables young children (ages 5-7) to create their own interactive stories and games.',
                'platform_type': 'Visual Programming',
                'base_url': 'https://www.scratchjr.org',
                'supported_languages': ['ScratchJr'],
                'requires_authentication': False,
                'supports_collaboration': False,
                'supports_file_upload': False,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    'mobile_app_available': True,
                    'offline_capable': True,
                    'project_templates': ['story', 'game', 'animation'],
                    'parent_controls': True
                },
                'icon': 'scratchjr',
                'color': '#FF6B35',
                'min_age': 5,
                'max_age': 7,
                'skill_levels': ['beginner'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'blockly',
                'display_name': 'Blockly',
                'description': 'A library that adds a visual code editor to web and mobile apps. Blockly generates clean, readable code in multiple programming languages.',
                'platform_type': 'Visual Programming',
                'base_url': 'https://developers.google.com/blockly',
                'supported_languages': ['JavaScript', 'Python', 'PHP', 'Lua', 'Dart'],
                'requires_authentication': False,
                'supports_collaboration': False,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'customizable_blocks': True,
                    'code_generation': True,
                    'multiple_languages': True,
                    'api_available': True
                },
                'icon': 'blockly',
                'color': '#4285F4',
                'min_age': 10,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate', 'advanced'],
                'is_active': True,
                'is_featured': False,
                'is_free': True
            },

            # Online IDEs
            {
                'name': 'replit',
                'display_name': 'Replit Online IDE',
                'description': 'A powerful, browser-based IDE that supports over 50 programming languages. Perfect for coding education and collaborative programming.',
                'platform_type': 'Online IDE',
                'base_url': 'https://replit.com',
                'api_endpoint': 'https://replit.com/data/repls',
                'supported_languages': ['Python', 'JavaScript', 'Java', 'C++', 'HTML/CSS', 'Go', 'Rust', 'Ruby', 'PHP', 'C#'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'max_projects_per_user': 1000,
                    'supported_frameworks': ['React', 'Django', 'Flask', 'Express', 'Vue', 'Angular'],
                    'database_support': True,
                    'deployment_enabled': True,
                    'ai_assistance': True,
                    'classroom_features': True
                },
                'icon': 'replit',
                'color': '#667EEA',
                'min_age': 12,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'trinket',
                'display_name': 'Trinket',
                'description': 'A simple, browser-based Python IDE perfect for education. Write, run, and share Python code instantly without any setup.',
                'platform_type': 'Online IDE',
                'base_url': 'https://trinket.io',
                'api_endpoint': 'https://trinket.io/api',
                'supported_languages': ['Python', 'HTML', 'CSS', 'JavaScript'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    'python_versions': ['Python 3'],
                    'turtle_graphics': True,
                    'sharing_enabled': True,
                    'embedding_enabled': True,
                    'classroom_features': True,
                    'templates_available': True,
                    'library_support': True
                },
                'icon': 'trinket',
                'color': '#00A8E8',
                'min_age': 10,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'codepen',
                'display_name': 'CodePen',
                'description': 'A social development environment for front-end designers and developers. Build and deploy a website, show off your work, build test cases to learn and debug.',
                'platform_type': 'Web Development',
                'base_url': 'https://codepen.io',
                'api_endpoint': 'https://codepen.io/api',
                'supported_languages': ['HTML', 'CSS', 'JavaScript'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'preprocessors': ['Sass', 'Less', 'Stylus', 'TypeScript', 'Babel'],
                    'external_libraries': True,
                    'templates_available': True,
                    'community_gallery': True,
                    'forking_enabled': True
                },
                'icon': 'codepen',
                'color': '#000000',
                'min_age': 14,
                'max_age': 18,
                'skill_levels': ['intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'jsfiddle',
                'display_name': 'JSFiddle',
                'description': 'An online code editor and playground for web developers. Test your JavaScript, CSS, HTML or CoffeeScript online with JSFiddle code editor.',
                'platform_type': 'Web Development',
                'base_url': 'https://jsfiddle.net',
                'supported_languages': ['HTML', 'CSS', 'JavaScript', 'CoffeeScript'],
                'requires_authentication': False,
                'supports_collaboration': False,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    'frameworks': ['jQuery', 'Vue', 'React', 'Angular'],
                    'libraries': ['Bootstrap', 'D3.js', 'Lodash'],
                    'sharing_enabled': True,
                    'embedding_enabled': True
                },
                'icon': 'jsfiddle',
                'color': '#0084FF',
                'min_age': 14,
                'max_age': 18,
                'skill_levels': ['intermediate', 'advanced'],
                'is_active': True,
                'is_featured': False,
                'is_free': True
            },

            # Design Tools
            {
                'name': 'figma',
                'display_name': 'Figma',
                'description': 'A collaborative interface design tool. Create, test, and ship better designs from start to finish with Figma.',
                'platform_type': 'Design Tool',
                'base_url': 'https://figma.com',
                'api_endpoint': 'https://api.figma.com',
                'supported_languages': [],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'real_time_collaboration': True,
                    'prototyping': True,
                    'design_systems': True,
                    'plugins_available': True,
                    'team_features': True
                },
                'icon': 'figma',
                'color': '#F24E1E',
                'min_age': 12,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'canva',
                'display_name': 'Canva',
                'description': 'A graphic design platform that allows users to create social media graphics, presentations, posters, documents and other visual content.',
                'platform_type': 'Design Tool',
                'base_url': 'https://canva.com',
                'api_endpoint': 'https://api.canva.com',
                'supported_languages': [],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    'templates_available': True,
                    'stock_photos': True,
                    'brand_kit': True,
                    'team_collaboration': True,
                    'presentation_mode': True
                },
                'icon': 'canva',
                'color': '#00C4CC',
                'min_age': 8,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },

            # Game Development
            {
                'name': 'unity',
                'display_name': 'Unity',
                'description': 'A cross-platform game engine developed by Unity Technologies. Used to create video games and simulations for computers, consoles, and mobile devices.',
                'platform_type': 'Game Engine',
                'base_url': 'https://unity.com',
                'supported_languages': ['C#', 'JavaScript'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'asset_store': True,
                    'cross_platform': True,
                    'vr_support': True,
                    '2d_3d_support': True,
                    'physics_engine': True
                },
                'icon': 'unity',
                'color': '#000000',
                'min_age': 14,
                'max_age': 18,
                'skill_levels': ['intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'godot',
                'display_name': 'Godot Engine',
                'description': 'A free and open-source game engine. Godot provides a huge set of common tools, so you can just focus on making your game without reinventing the wheel.',
                'platform_type': 'Game Engine',
                'base_url': 'https://godotengine.org',
                'supported_languages': ['GDScript', 'C#', 'C++'],
                'requires_authentication': False,
                'supports_collaboration': False,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'open_source': True,
                    'lightweight': True,
                    'node_based': True,
                    '2d_3d_support': True,
                    'export_templates': True
                },
                'icon': 'godot',
                'color': '#478CBF',
                'min_age': 14,
                'max_age': 18,
                'skill_levels': ['intermediate', 'advanced'],
                'is_active': True,
                'is_featured': False,
                'is_free': True
            },

            # Data Science
            {
                'name': 'jupyter',
                'display_name': 'Jupyter Notebook',
                'description': 'An open-source web application that allows you to create and share documents that contain live code, equations, visualizations and narrative text.',
                'platform_type': 'Data Science',
                'base_url': 'https://jupyter.org',
                'supported_languages': ['Python', 'R', 'Julia', 'Scala', 'JavaScript'],
                'requires_authentication': False,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'kernel_support': True,
                    'widgets_available': True,
                    'nbconvert': True,
                    'nbviewer': True,
                    'jupyterlab': True
                },
                'icon': 'jupyter',
                'color': '#F37626',
                'min_age': 16,
                'max_age': 18,
                'skill_levels': ['intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'colab',
                'display_name': 'Google Colab',
                'description': 'A free Jupyter notebook environment that runs entirely in the cloud. Perfect for machine learning, data analysis and education.',
                'platform_type': 'Data Science',
                'base_url': 'https://colab.research.google.com',
                'supported_languages': ['Python'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'gpu_support': True,
                    'tpu_support': True,
                    'google_drive_integration': True,
                    'github_integration': True,
                    'pre_installed_libraries': True
                },
                'icon': 'colab',
                'color': '#F9AB00',
                'min_age': 16,
                'max_age': 18,
                'skill_levels': ['intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },

            # Hardware/Robotics
            {
                'name': 'arduino',
                'display_name': 'Arduino IDE',
                'description': 'An open-source electronics platform based on easy-to-use hardware and software. Perfect for learning electronics and programming.',
                'platform_type': 'Hardware IDE',
                'base_url': 'https://www.arduino.cc',
                'supported_languages': ['C++', 'Arduino'],
                'requires_authentication': False,
                'supports_collaboration': False,
                'supports_file_upload': True,
                'supports_live_preview': False,
                'supports_version_control': True,
                'platform_config': {
                    'board_support': True,
                    'library_manager': True,
                    'serial_monitor': True,
                    'plotter': True,
                    'examples_available': True
                },
                'icon': 'arduino',
                'color': '#00979D',
                'min_age': 12,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'tinkercad',
                'display_name': 'Tinkercad',
                'description': 'A free, easy-to-use app for 3D design, electronics, and coding. Perfect for beginners to learn 3D modeling and circuit design.',
                'platform_type': 'Hardware IDE',
                'base_url': 'https://www.tinkercad.com',
                'supported_languages': ['Arduino', 'JavaScript'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    '3d_modeling': True,
                    'circuit_simulation': True,
                    'code_blocks': True,
                    'lessons_available': True,
                    'classroom_integration': True,
                    'virtual_arduino': True
                },
                'icon': 'tinkercad',
                'color': '#FF6900',
                'min_age': 8,
                'max_age': 16,
                'skill_levels': ['beginner', 'intermediate'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'wokwi',
                'display_name': 'Wokwi Arduino Simulator',
                'description': 'Online Arduino simulator that lets you build, test and share your projects in the browser. No hardware needed!',
                'platform_type': 'Hardware IDE',
                'base_url': 'https://wokwi.com',
                'api_endpoint': 'https://wokwi.com/api',
                'supported_languages': ['Arduino', 'C++'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'virtual_arduino': True,
                    'real_time_simulation': True,
                    'component_library': True,
                    'sharing_enabled': True,
                    'project_templates': True,
                    'debugging_tools': True,
                    'serial_monitor': True
                },
                'icon': 'wokwi',
                'color': '#4CAF50',
                'min_age': 12,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'arduino_create',
                'display_name': 'Arduino Create',
                'description': 'Cloud-based Arduino IDE with built-in simulation capabilities. Create, code, and simulate Arduino projects online.',
                'platform_type': 'Hardware IDE',
                'base_url': 'https://create.arduino.cc',
                'api_endpoint': 'https://api.arduino.cc',
                'supported_languages': ['Arduino', 'C++'],
                'requires_authentication': True,
                'supports_collaboration': True,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': True,
                'platform_config': {
                    'cloud_ide': True,
                    'virtual_arduino': True,
                    'board_manager': True,
                    'library_manager': True,
                    'project_sharing': True,
                    'classroom_integration': True,
                    'offline_sync': True
                },
                'icon': 'arduino_create',
                'color': '#00979D',
                'min_age': 12,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True
            },
            {
                'name': 'virtual_breadboard',
                'display_name': 'Virtual Breadboard',
                'description': 'Professional circuit simulation software with Arduino support. Perfect for advanced electronics education and prototyping.',
                'platform_type': 'Hardware IDE',
                'base_url': 'https://www.virtualbreadboard.com',
                'supported_languages': ['Arduino', 'C++'],
                'requires_authentication': False,
                'supports_collaboration': False,
                'supports_file_upload': True,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    'professional_simulation': True,
                    'arduino_support': True,
                    'component_library': True,
                    'oscilloscope': True,
                    'logic_analyzer': True,
                    'advanced_debugging': True
                },
                'icon': 'virtual_breadboard',
                'color': '#8BC34A',
                'min_age': 16,
                'max_age': 18,
                'skill_levels': ['intermediate', 'advanced'],
                'is_active': True,
                'is_featured': False,
                'is_free': False
            }
        ]

        created_count = 0
        updated_count = 0

        for platform_data in platforms_data:
            platform, created = ProjectPlatform.objects.update_or_create(
                name=platform_data['name'],
                defaults=platform_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created platform: {platform.display_name}')
            else:
                updated_count += 1
                self.stdout.write(f'Updated platform: {platform.display_name}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed {len(platforms_data)} platforms. '
                f'Created: {created_count}, Updated: {updated_count}'
            )
        )

        # Add internal Ace Pyodide platform
        ace_pyodide_platform, created = ProjectPlatform.objects.update_or_create(
            name='ace_pyodide',
            defaults={
                'display_name': 'Ace Pyodide',
                'description': 'Internal code editor with Python execution using Pyodide. Students write and run code directly in the browser without external platforms.',
                'platform_type': 'Online IDE',
                'base_url': '/student/ide',  # Internal route
                'api_endpoint': '',
                'supported_languages': ['python', 'javascript'],
                'requires_authentication': True,
                'supports_collaboration': False,
                'supports_file_upload': False,
                'supports_live_preview': True,
                'supports_version_control': False,
                'platform_config': {
                    'is_internal': True,
                    'editor': 'ace',
                    'runtime': 'pyodide',
                    'submission_type': 'code'
                },
                'icon': 'code',
                'color': '#6366f1',
                'logo_url': '',
                'min_age': 8,
                'max_age': 18,
                'skill_levels': ['beginner', 'intermediate', 'advanced'],
                'is_active': True,
                'is_featured': True,
                'is_free': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created Ace Pyodide platform'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Updated Ace Pyodide platform'))

        # Display summary by platform type
        self.stdout.write('\nPlatform Summary by Type:')
        platform_types = ProjectPlatform.objects.values_list('platform_type', flat=True).distinct()
        for platform_type in platform_types:
            count = ProjectPlatform.objects.filter(platform_type=platform_type).count()
            self.stdout.write(f'  {platform_type}: {count} platforms')
