import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
	site: 'https://opencitations.github.io',
	base: '/lode',

	integrations: [
		starlight({
			title: 'LODE 2.0',
			description: 'Live OWL Documentation Environment — extract and document RDF/OWL/SKOS semantic artefacts as browsable HTML.',

			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/opencitations/lode' },
			],

			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Installation', slug: 'getting_started' },
					],
				},
				{
					label: 'Usage',
					items: [
						{ label: 'Web Form', slug: 'usage/web_form' },
						{ label: 'CLI', slug: 'usage/cli' },
						{ label: 'Docker', slug: 'usage/docker' },
					],
				},
				{
					label: 'API Reference',
					items: [
						{ label: 'Endpoints', slug: 'api/endpoints' },
					],
				},
			],
		}),
	],
});