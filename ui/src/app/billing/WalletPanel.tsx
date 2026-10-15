"use client";

import { CreditCard, Wallet } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import {
    getWalletOverviewApiV1OrganizationsBillingWalletGet,
    listWalletTransactionsApiV1OrganizationsBillingWalletTransactionsGet,
    listWalletUsageApiV1OrganizationsBillingWalletUsageGet,
    updateWalletSettingsApiV1OrganizationsBillingSettingsPut,
} from "@/client/sdk.gen";
import type {
    UsageRecordResponse,
    WalletOverviewResponse,
    WalletTransactionResponse,
} from "@/client/types.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { detailFromError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/dateTime";

const formatCents = (cents?: number | null) =>
    new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(
        (cents ?? 0) / 100,
    );

const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
};

export function WalletPanel() {
    const { user, loading: authLoading } = useAuth();
    const hasFetched = useRef(false);

    const [overview, setOverview] = useState<WalletOverviewResponse | null>(null);
    const [transactions, setTransactions] = useState<WalletTransactionResponse[]>([]);
    const [usage, setUsage] = useState<UsageRecordResponse[]>([]);
    const [loading, setLoading] = useState(true);

    const [autoEnabled, setAutoEnabled] = useState(false);
    const [threshold, setThreshold] = useState(0);
    const [amount, setAmount] = useState(0);
    const [saving, setSaving] = useState(false);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        const [overviewRes, txRes, usageRes] = await Promise.all([
            getWalletOverviewApiV1OrganizationsBillingWalletGet(),
            listWalletTransactionsApiV1OrganizationsBillingWalletTransactionsGet({ query: { limit: 20 } }),
            listWalletUsageApiV1OrganizationsBillingWalletUsageGet({ query: { limit: 20 } }),
        ]);

        const error = overviewRes.error ?? txRes.error ?? usageRes.error;
        if (error) {
            toast.error(detailFromError(error, "Failed to load wallet"));
        }
        if (overviewRes.data) {
            setOverview(overviewRes.data);
            setAutoEnabled(overviewRes.data.settings.auto_recharge_enabled);
            setThreshold(overviewRes.data.settings.auto_recharge_threshold_cents);
            setAmount(overviewRes.data.settings.auto_recharge_amount_cents);
        }
        if (txRes.data) setTransactions(txRes.data.transactions);
        if (usageRes.data) setUsage(usageRes.data.usage_records);
        setLoading(false);
    }, []);

    useEffect(() => {
        if (authLoading || !user || hasFetched.current) return;
        hasFetched.current = true;
        fetchAll();
    }, [authLoading, user, fetchAll]);

    const handleSaveAutoRecharge = async () => {
        setSaving(true);
        const response = await updateWalletSettingsApiV1OrganizationsBillingSettingsPut({
            body: {
                auto_recharge_enabled: autoEnabled,
                auto_recharge_threshold_cents: threshold,
                auto_recharge_amount_cents: amount,
            },
        });
        setSaving(false);
        if (response.error) {
            toast.error(detailFromError(response.error, "Failed to save auto-recharge settings"));
            return;
        }
        toast.success("Auto-recharge settings saved");
    };

    if (loading) {
        return (
            <Card>
                <CardContent className="space-y-3 pt-6">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-24 w-full" />
                </CardContent>
            </Card>
        );
    }

    if (!overview) {
        return null;
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Wallet className="h-5 w-5 text-muted-foreground" />
                    Wallet
                </CardTitle>
                <CardDescription>
                    Local usage ledger and top-ups. Billing enforcement is controlled by the platform.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                <div className="grid gap-4 sm:grid-cols-3">
                    <div>
                        <p className="text-sm text-muted-foreground">Balance</p>
                        <p className="text-2xl font-semibold">{formatCents(overview.balance_cents)}</p>
                    </div>
                    <div>
                        <p className="text-sm text-muted-foreground">Rate</p>
                        <p className="text-2xl font-semibold">
                            {formatCents(overview.settings.rate_cents_per_minute)}/min
                        </p>
                    </div>
                    <div>
                        <p className="text-sm text-muted-foreground">Usage (all time)</p>
                        <p className="text-2xl font-semibold">{formatCents(overview.totals.total_amount_cents)}</p>
                        <p className="text-xs text-muted-foreground">
                            {overview.totals.call_count} calls · {formatDuration(overview.totals.total_duration_seconds)}
                        </p>
                    </div>
                </div>

                {overview.payment_links && overview.payment_links.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                        {overview.payment_links.map((link) => (
                            <Button key={link.url} asChild>
                                <a href={link.url} target="_blank" rel="noopener noreferrer">
                                    <CreditCard className="h-4 w-4 mr-2" />
                                    {link.label || `Top up ${formatCents(link.amount_cents)}`}
                                </a>
                            </Button>
                        ))}
                    </div>
                )}

                <div className="rounded-lg border p-4 space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="font-medium">Auto-recharge</p>
                            <p className="text-sm text-muted-foreground">
                                Enables topping up when the balance crosses the threshold.
                            </p>
                        </div>
                        <Switch checked={autoEnabled} onCheckedChange={setAutoEnabled} />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-3">
                        <div className="space-y-1">
                            <Label htmlFor="wallet-threshold">Threshold (cents)</Label>
                            <Input
                                id="wallet-threshold"
                                type="number"
                                value={threshold}
                                onChange={(e) => setThreshold(Number(e.target.value))}
                            />
                        </div>
                        <div className="space-y-1">
                            <Label htmlFor="wallet-amount">Recharge amount (cents)</Label>
                            <Input
                                id="wallet-amount"
                                type="number"
                                value={amount}
                                onChange={(e) => setAmount(Number(e.target.value))}
                            />
                        </div>
                        <div className="flex items-end">
                            <Button variant="outline" onClick={handleSaveAutoRecharge} disabled={saving}>
                                {saving ? "Saving..." : "Save"}
                            </Button>
                        </div>
                    </div>
                </div>

                <div>
                    <p className="mb-2 font-medium">Recent transactions</p>
                    {transactions.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No transactions yet.</p>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Date</TableHead>
                                    <TableHead>Description</TableHead>
                                    <TableHead className="text-right">Amount</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {transactions.map((tx) => (
                                    <TableRow key={tx.id}>
                                        <TableCell>{formatDateTime(tx.created_at)}</TableCell>
                                        <TableCell>{tx.description || tx.kind}</TableCell>
                                        <TableCell
                                            className={`text-right ${tx.amount_cents < 0 ? "text-destructive" : "text-green-600"}`}
                                        >
                                            {formatCents(tx.amount_cents)}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </div>

                <div>
                    <p className="mb-2 font-medium">Usage history</p>
                    {usage.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No usage recorded yet.</p>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Date</TableHead>
                                    <TableHead>Duration</TableHead>
                                    <TableHead className="text-right">Charged</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {usage.map((record) => (
                                    <TableRow key={record.id}>
                                        <TableCell>{formatDateTime(record.created_at)}</TableCell>
                                        <TableCell>{formatDuration(record.duration_seconds)}</TableCell>
                                        <TableCell className="text-right">
                                            {formatCents(record.amount_cents)}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
