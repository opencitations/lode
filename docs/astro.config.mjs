import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import rehypeExternalLinks from 'rehype-external-links';

export default defineConfig({
	markdown: {
		rehypePlugins: [
			[rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]
		],
	},
	site: 'https://opencitations.github.io',
	base: '/python-package-template',

	integrations: [
		starlight({
			title: 'Python Package Template',
			description: 'A template for creating Python packages with UV, pytest, and Starlight documentation',

			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/opencitations/python-package-template' },
			],

			sidebar: [
				{
					label: 'Guides',
					items: [
						{ label: 'Getting started', slug: 'getting_started' },
					],
				},
			],
		}),
	],
});
