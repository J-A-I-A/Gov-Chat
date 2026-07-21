<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { setPassword } from '$lib/apis/auths';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME } from '$lib/stores';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	const i18n = getContext('i18n');

	let loaded = false;
	let loading = false;
	let done = false;

	let token = '';
	let password = '';
	let confirmPassword = '';

	const submitHandler = async () => {
		if (password !== confirmPassword) {
			toast.error($i18n.t('Passwords do not match.'));
			return;
		}

		loading = true;
		const res = await setPassword(token, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		loading = false;

		if (res) {
			done = true;
			toast.success($i18n.t('Your password has been set. You can now sign in.'));
			setTimeout(() => goto('/auth'), 1500);
		}
	};

	onMount(() => {
		token = $page.url.searchParams.get('token') ?? '';
		loaded = true;
	});
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
</svelte:head>

<div class="w-full h-screen max-h-[100dvh] text-white relative">
	<div class="w-full h-full absolute top-0 left-0 bg-white dark:bg-black"></div>
	<div class="w-full absolute top-0 left-0 right-0 h-8 drag-region" />

	{#if loaded}
		<div
			class="fixed bg-transparent min-h-screen w-full flex justify-center font-primary z-50 text-black dark:text-white"
		>
			<div class="w-full px-10 min-h-screen flex flex-col text-center">
				<div class="my-auto flex flex-col justify-center items-center">
					<div class="sm:max-w-md my-auto pb-10 w-full dark:text-gray-100">
						<div class="flex justify-center mb-6">
							<img
								crossorigin="anonymous"
								src="{WEBUI_BASE_URL}/static/favicon.png"
								class="size-16 rounded-full"
								alt="{$WEBUI_NAME} logo"
							/>
						</div>

						{#if !token}
							<div class="text-2xl font-medium mb-2">{$i18n.t('Invalid link')}</div>
							<div class="text-sm text-gray-500 dark:text-gray-400">
								{$i18n.t('This password link is invalid or has expired.')}
							</div>
							<div class="mt-4 text-sm text-center">
								<a class="font-medium underline" href="/auth">{$i18n.t('Back to sign in')}</a>
							</div>
						{:else if done}
							<div class="text-2xl font-medium mb-2">{$i18n.t('Password updated')}</div>
							<div class="text-sm text-gray-500 dark:text-gray-400">
								{$i18n.t('Redirecting you to sign in…')}
							</div>
						{:else}
							<form class="flex flex-col justify-center" on:submit|preventDefault={submitHandler}>
								<div class="mb-1">
									<div class="text-2xl font-medium">{$i18n.t('Set a new password')}</div>
								</div>

								<div class="flex flex-col mt-4">
									<div class="mb-2">
										<label for="new-password" class="text-sm font-medium text-left mb-1 block">
											{$i18n.t('New Password')}
										</label>
										<SensitiveInput
											bind:value={password}
											type="password"
											id="new-password"
											class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-600"
											placeholder={$i18n.t('Enter Your Password')}
											autocomplete="new-password"
											name="new-password"
											required
										/>
									</div>

									<div>
										<label for="confirm-password" class="text-sm font-medium text-left mb-1 block">
											{$i18n.t('Confirm Password')}
										</label>
										<SensitiveInput
											bind:value={confirmPassword}
											type="password"
											id="confirm-password"
											class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-600"
											placeholder={$i18n.t('Confirm Your Password')}
											autocomplete="new-password"
											name="confirm-password"
											required
										/>
									</div>
								</div>

								<div class="mt-5">
									<button
										class="bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5 flex items-center justify-center gap-2 {loading
										? 'cursor-not-allowed'
										: ''}"
										type="submit"
										disabled={loading}
									>
										{$i18n.t('Set password')}
										{#if loading}
											<Spinner className="size-4" />
										{/if}
									</button>

									<div class="mt-4 text-sm text-center">
										<a class="font-medium underline" href="/auth">{$i18n.t('Back to sign in')}</a>
									</div>
								</div>
							</form>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
